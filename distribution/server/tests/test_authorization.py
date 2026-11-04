import hashlib
import json
from uuid import UUID, uuid4

import httpx2
import pytest
from fault_support import cycle, record, req
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from agents_memory_collab.client import Remote
from agents_memory_collab.models import Failure


async def team(system, tmp_path):
    a, b, owner = await system.pair(tmp_path)
    member_remote, member = await system.account('Synthetic Member')
    t = (await req(a.remote, '/v1/teams', {'name': 'Audit Team'}))['id']
    base = '/v1/teams/'+t
    project = (await req(a.remote, base+'/projects', {'name': 'Allowed'}))['id']
    secret = (await req(a.remote, base+'/projects', {'name': 'Not Granted'}))['id']
    invite = (await req(a.remote, base+'/invites', {'projects': [project]}))['invite']
    await req(member_remote, '/v1/invites/accept', {'invite': invite})
    shared = a.stage('share-me', 'SYNTHETIC SHARED DECISION')['memory_id']
    private = a.stage('private', 'SYNTHETIC PRIVATE DECISION')['memory_id']
    await cycle(a); await cycle(b)
    await req(a.remote, base+'/sharing', {'mappings': [
        {'source_project': 'share-me', 'project_id': project},
        {'source_project': 'private', 'project_id': secret}]}, 'PUT')
    return a, b, owner, member_remote, member, t, project, secret, shared, private


@pytest.mark.parametrize('action', ['unshare', 'leave', 'remove_member', 'revoke_key', 'reader_grant', 'author_grant'])
async def test_new_queries_after_revocation(system, tmp_path, action):
    a, _b, owner, remote, member, t, project, secret, shared, _private = await team(system, tmp_path)
    base = '/v1/teams/'+t
    query = {'query': 'DECISION'}
    assert [x['id'] for x in (await req(remote, base+'/search', query))['memories']] == [shared]
    assert len((await req(remote, base+'/brief?project='+project))['items']) == 1
    assert (await req(remote, base+'/brief?project='+secret))['items'] == []
    assert (await req(remote, '/v1/recall', query))['memories'] == []
    mechanism = 'public HTTP API'
    if action == 'unshare':
        await req(a.remote, base+'/sharing', {'mappings': []}, 'PUT')
    elif action == 'leave':
        await req(remote, base+'/leave', {})
    elif action == 'remove_member':
        await req(a.remote, base+'/members/'+str(member.user_id), method='DELETE')
    elif action == 'revoke_key':
        await req(remote, '/v1/devices/'+str(member.credential_id), method='DELETE')
    elif action == 'reader_grant':
        mechanism = 'operator SQL; no grant-replacement HTTP API exists'
        await system.store.pool.execute('DELETE FROM am_collab.grants WHERE user_id=$1', member.user_id)
    elif action == 'author_grant':
        # A member author requires a grant; owner is intentionally exempt.
        mechanism = 'operator SQL role/grant change; no equivalent HTTP API'
        await system.store.pool.execute("UPDATE am_collab.members SET role='member' WHERE user_id=$1 AND team_id=$2", owner.user_id, UUID(t))
    observed = []
    for path, payload, field in [(base+'/search', query, 'memories'), (base+'/brief?project='+project, None, 'items')]:
        try:
            value = await req(remote, path, payload)
            observed.append({'path': path, 'result': value})
            assert value[field] == [], 'I5: content disclosed after completed revocation'
        except Failure as exc:
            observed.append({'path': path, 'status': exc.status, 'error': exc.code})
            assert exc.status in (401, 403, 404)
    record('revoke_'+action, {'mechanism': mechanism, 'new_queries': observed, 'previously_delivered_copies_not_erased': True})


async def db_fingerprint(system):
    tables = await system.store.pool.fetch("SELECT tablename FROM pg_tables WHERE schemaname='am_collab' ORDER BY tablename")
    data = {}
    for table in tables:
        rows = await system.store.pool.fetch('SELECT row_to_json(t)::text AS value FROM am_collab.'+table['tablename']+' t')
        data[table['tablename']] = sorted(row['value'] for row in rows)
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


async def test_read_only_key_all_mutations_and_viewer_scope(system, tmp_path):
    a, _b, owner, member_remote, member, t, project, _secret, _shared, _private = await team(system, tmp_path)
    base = '/v1/teams/'+t
    key = await req(a.remote, '/v1/devices', {'name': 'Read Only Owner', 'writable': False})
    read = Remote(a.remote.url, key['token'])
    invitation = (await req(a.remote, base+'/invites', {'role': 'viewer', 'projects': [project]}))['invite']
    op = {'op_id': str(uuid4()), 'memory_id': str(uuid4()), 'project': 'share-me', 'text': 'forbidden'}
    cases = [('/v1/devices', {'name': 'escalation', 'writable': True}, 'POST'),
        ('/v1/devices/'+str(owner.credential_id), None, 'DELETE'),
        ('/v1/preferences', {'upload_prompts': True}, 'PUT'),
        ('/v1/sync/ops', {'operations': [op]}, 'POST'),
        ('/v1/teams', {'name': 'forbidden'}, 'POST'),
        (base+'/projects', {'name': 'forbidden'}, 'POST'),
        (base+'/invites', {'projects': [project]}, 'POST'),
        ('/v1/invites/accept', {'invite': invitation}, 'POST'),
        (base+'/sharing', {'mappings': []}, 'PUT'),
        (base+'/leave', {}, 'POST'),
        (base+'/members/'+str(member.user_id), None, 'DELETE')]
    before = await db_fingerprint(system)
    statuses = []
    for path, body, method in cases:
        with pytest.raises(Failure) as exc:
            await req(read, path, body, method)
        assert exc.value.status == 403 and exc.value.code in {'read_only_credential', 'key_manager_required'}
        statuses.append({'path': path, 'status': exc.value.status})
    assert await db_fingerprint(system) == before
    viewer, _viewer_actor = await system.account('Synthetic Viewer')
    await req(viewer, '/v1/invites/accept', {'invite': invitation})
    for path, body, method in [(base+'/projects', {'name': 'denied'}, 'POST'),
        (base+'/invites', {'projects': [project]}, 'POST'),
        (base+'/members/'+str(member.user_id), None, 'DELETE'),
        (base+'/sharing', {'mappings': [{'source_project': 'mine', 'project_id': project}]}, 'PUT')]:
        before = await db_fingerprint(system)
        with pytest.raises(Failure) as exc:
            await req(viewer, path, body, method)
        assert exc.value.status == 403
        assert await db_fingerprint(system) == before
    with pytest.raises(Failure) as exc:
        await req(member_remote, '/v1/devices/'+str(owner.credential_id), method='DELETE')
    assert exc.value.status == 404
    assert (await req(a.remote, '/v1/me'))['user_id'] == str(owner.user_id)
    record('authorization_matrix', {'read_only_mutations': statuses, 'database_unchanged': True,
        'viewer_admin_mutations_denied': 4, 'cross_account_key_revoke': 404,
        'project_scoped_api_keys': 'not implemented: credentials have account scope and writable bit'})


async def test_real_mcp_tools_and_new_calls_after_unshare(system, tmp_path):
    a, _b, _owner, remote, _member, t, project, _secret, shared, _private = await team(system, tmp_path)
    async with (
        httpx2.AsyncClient(trust_env=False, headers={'Authorization': 'Bearer '+remote.token}) as http,
        streamable_http_client(system.url+'/mcp', http_client=http) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        params = {'team_id': t, 'query': 'DECISION'}
        found = await session.call_tool('team_search', params)
        assert not found.is_error
        assert [m['id'] for m in json.loads(found.content[0].text)['memories']] == [shared]
        brief = await session.call_tool('team_brief', {'team_id': t, 'project_id': project})
        assert len(json.loads(brief.content[0].text)['items']) == 1
        await req(a.remote, '/v1/teams/'+t+'/sharing', {'mappings': []}, 'PUT')
        found = await session.call_tool('team_search', params)
        brief = await session.call_tool('team_brief', {'team_id': t, 'project_id': project})
        assert json.loads(found.content[0].text)['memories'] == []
        assert json.loads(brief.content[0].text)['items'] == []
        record('real_mcp_revocation', {'before_shared_results': 1, 'after_search': 0, 'after_brief': 0, 'same_connection_new_tool_calls': True})
