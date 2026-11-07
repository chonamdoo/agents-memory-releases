"""Regression contracts from the independent Astra/Fable counterexamples."""
import asyncio
import json
import subprocess
import threading
from uuid import uuid4

import pytest
from fault_support import DSN, PG, cycle, durable, local, record, req
from engine_double import ProtocolEngine

from agents_memory_collab.client import Remote
from agents_memory_collab.models import Failure


@pytest.mark.parametrize('kind', ['memory', 'summary', 'prompt'])
async def test_binding_precedes_queue_and_account_switch_never_transmits(system, tmp_path, kind):
    remote, _ = await system.account()
    a = system.replica(tmp_path/'a.sqlite', remote)
    with pytest.raises(Failure, match='setup_required_before_queueing'):
        a.stage('selected-project', 'private synthetic text', kind=kind, allow_prompts=True)
    assert a.db.execute('SELECT count(*) FROM outbox').fetchone()[0] == 0
    await asyncio.to_thread(a.connect)
    staged = a.stage('selected-project', 'private synthetic text', kind=kind, allow_prompts=True)
    other, outsider = await system.account('Other account')
    a.remote = other
    with pytest.raises(Failure, match='verify_destination'):
        a.stage('selected-project', 'must not queue')
    with pytest.raises(Failure, match='destination_changed'):
        await cycle(a)
    assert await durable(system, outsider.user_id) == {}
    assert a.status()['pending'][0]['op_id'] == staged['op_id']
    assert not [e for e in system.proxy.events if e['path'].endswith('/ops')]


async def test_server_switch_before_first_sync_never_uploads(system, tmp_path):
    a, _, actor = await system.pair(tmp_path)
    a.stage('app', 'private synthetic text')
    # A second origin fronts the same backend: changing origin still needs a new replica.
    from fault_support import WireProxy
    alternate = WireProxy(f'127.0.0.1:{system.port}')
    try:
        a.remote = Remote(alternate.url, a.remote.token)
        with pytest.raises(Failure, match='destination_changed'):
            await cycle(a)
        assert not await durable(system, actor.user_id)
        assert not [e for e in alternate.events if e['path'].endswith('/ops')]
    finally:
        await asyncio.to_thread(alternate.close)


@pytest.mark.parametrize('kind', ['memory', 'summary', 'prompt'])
async def test_lost_socket_ack_preserves_meaning_and_applies_once_after_restart(system, tmp_path, kind):
    a, b, actor = await system.pair(tmp_path)
    await req(a.remote, '/v1/preferences', {'upload_prompts': True}, 'PUT')
    intent = a.stage('scope-a', 'Synthetic Ω content', kind=kind, allow_prompts=True,
                     session_id='session-a', source_id='source-a')
    system.proxy.drop_next_push = True
    with pytest.raises(OSError):
        await cycle(a)
    assert a.status()['pending'][0]['op_id'] == intent['op_id']
    assert len(await durable(system, actor.user_id)) == 1
    remote = a.remote
    a.close()
    a = system.replica(tmp_path/'a.sqlite', remote)
    await cycle(a)
    await cycle(b)
    assert a.status()['pending'] == b.status()['pending'] == []
    assert local(a) == local(b) == await durable(system, actor.user_id)
    row = b.list_memories()[0]
    assert (row['project'], row['kind'], row['text'], row['session_id'], row['source_id']) == ('scope-a', kind, 'Synthetic Ω content', 'session-a', 'source-a')
    assert await system.store.pool.fetchval('SELECT count(*) FROM am_collab.changes') == 1
    assert sum(not e['delivered'] for e in system.proxy.events) == 1
    assert (await req(b.remote, '/v1/recall', {'query': 'Synthetic', 'project': 'scope-a'}))['memories'] or kind == 'prompt'


async def test_applied_operation_retry_survives_projection_drift_and_restart(system, tmp_path):
    a, b, actor = await system.pair(tmp_path)
    operation_id = str(uuid4())
    first = a.stage('app', 'original retry payload', op_id=operation_id)
    await cycle(a)
    await cycle(b)
    b.stage('app', 'later revision', memory_id=first['memory_id'],
            session_id='later-session', source_id='later-source')
    await cycle(b)
    await cycle(a)
    before = await durable(system, actor.user_id)
    assert before[first['memory_id']]['revision'] == 2
    remote = a.remote
    a.close()
    a = system.replica(tmp_path/'a.sqlite', remote)
    pushes = sum(event['path'] == '/v1/sync/ops' for event in system.proxy.events)

    retried = a.stage('app', 'original retry payload', op_id=operation_id)

    assert retried == {'memory_id': first['memory_id'], 'op_id': operation_id,
                       'queued': False, 'state': 'applied', 'reason': None}
    assert a.outcome(operation_id)['state'] == 'applied'
    assert a.status()['pending'] == []
    await cycle(a)
    assert local(a) == before == await durable(system, actor.user_id)
    assert sum(event['path'] == '/v1/sync/ops' for event in system.proxy.events) == pushes
    assert await system.store.pool.fetchval('SELECT count(*) FROM am_collab.changes') == 2
    assert await system.store.pool.fetchval('SELECT count(*) FROM am_collab.memory_jobs') == 2


async def test_pending_operation_retry_keeps_null_metadata_after_projection_drift(system, tmp_path):
    a, b, actor = await system.pair(tmp_path)
    memory_id = a.stage('app', 'initial revision')['memory_id']
    await cycle(a)
    await cycle(b)
    operation_id = str(uuid4())
    a.stage('app', 'pending retry payload', memory_id=memory_id, op_id=operation_id)
    original_body = a.db.execute('SELECT body FROM outbox').fetchone()[0]
    original = json.loads(original_body)
    assert (original['base_revision'], original['session_id'], original['source_id']) == (1, None, None)
    b.stage('app', 'winning revision', memory_id=memory_id,
            session_id='later-session', source_id='later-source')
    await cycle(b)
    await cycle(a, pull_only=True)

    retried = a.stage('app', 'pending retry payload', memory_id=memory_id, op_id=operation_id)

    assert retried['state'] == 'processing'
    assert a.db.execute('SELECT body FROM outbox').fetchone()[0] == original_body
    result = await cycle(a)
    assert result['state'] == 'needs_review'
    assert a.outcome(operation_id) == {
        'op_id': operation_id, 'state': 'needs_review', 'reason': 'revision_conflict'}
    saved = a.list_memories()[0]
    assert (saved['text'], saved['revision'], saved['session_id'], saved['source_id']) == (
        'winning revision', 2, 'later-session', 'later-source')
    assert local(a) == await durable(system, actor.user_id)
    assert await system.store.pool.fetchval('SELECT count(*) FROM am_collab.memory_jobs') == 2
    assert await system.store.pool.fetchval('SELECT count(*) FROM am_collab.changes') == 2




async def test_changed_retry_cannot_inherit_applied_operation_receipt(system, tmp_path):
    a, _, actor = await system.pair(tmp_path)
    arguments = {'memory_id': str(uuid4()), 'op_id': str(uuid4()), 'base_revision': 0,
                 'origin': 'user_prompt'}
    assert a._state()['origin_aware'] == 0
    a.stage('app', 'original retry payload', **arguments)
    await cycle(a)
    before = await durable(system, actor.user_id)
    pushes = sum(event['path'] == '/v1/sync/ops' for event in system.proxy.events)
    with pytest.raises(Failure, match='^operation_id_reused$'):
        a.stage('app', 'changed retry payload', **arguments)
    with pytest.raises(Failure, match='^operation_id_reused$'):
        a.stage('app', 'original retry payload', **{**arguments, 'memory_id': str(uuid4())})
    with pytest.raises(Failure, match='^operation_id_reused$'):
        a.stage('app', 'original retry payload', **{**arguments, 'origin': None})
    assert a.outcome(arguments['op_id']) == {'op_id': arguments['op_id'], 'state': 'applied', 'reason': None}
    assert a.status()['pending'] == []
    await cycle(a)
    assert await durable(system, actor.user_id) == before
    assert sum(event['path'] == '/v1/sync/ops' for event in system.proxy.events) == pushes
    assert await system.store.pool.fetchval('SELECT count(*) FROM am_collab.memory_jobs') == 1
    assert await system.store.pool.fetchval('SELECT count(*) FROM am_collab.changes') == 1


async def test_concurrent_same_operation_uses_one_queue_and_server_result(system, tmp_path):
    a, _, actor = await system.pair(tmp_path)
    other = system.replica(a.path, Remote(a.remote.url, a.remote.token))
    operation_id = str(uuid4())
    barrier = threading.Barrier(2)

    def stage(replica):
        barrier.wait(timeout=10)
        return replica.stage('app', 'concurrent retry payload', op_id=operation_id)

    first, second = await asyncio.gather(asyncio.to_thread(stage, a), asyncio.to_thread(stage, other))
    assert first['op_id'] == second['op_id'] == operation_id
    assert first['memory_id'] == second['memory_id']
    assert a.db.execute('SELECT count(*) FROM outbox').fetchone()[0] == 1
    await cycle(a)
    await cycle(other)
    assert a.status()['pending'] == other.status()['pending'] == []
    assert a.outcome(operation_id) == other.outcome(operation_id) == {
        'op_id': operation_id, 'state': 'applied', 'reason': None}
    assert local(a) == local(other) == await durable(system, actor.user_id)
    assert sum(event['path'] == '/v1/sync/ops' for event in system.proxy.events) == 1
    assert await system.store.pool.fetchval('SELECT count(*) FROM am_collab.memory_jobs') == 1
    assert await system.store.pool.fetchval('SELECT count(*) FROM am_collab.changes') == 1


async def test_legacy_pending_retry_preserves_wire_body_across_origin_upgrade(system, tmp_path):
    a, _, actor = await system.pair(tmp_path)
    memory_id = a.stage('app', 'previous revision', session_id='previous-session',
                        source_id='previous-source')['memory_id']
    await cycle(a)
    legacy = {'op_id': str(uuid4()), 'memory_id': memory_id, 'project': 'app', 'kind': 'memory',
              'base_revision': 1, 'deleted': False, 'text': 'legacy Ω retry payload',
              'session_id': None, 'source_id': None, 'origin': None}
    original_body = json.dumps(legacy, ensure_ascii=False)
    with a.transaction():
        a.db.execute('INSERT INTO outbox(op_id,memory_id,body) VALUES(?,?,?)',
                     (legacy['op_id'], memory_id, original_body))
    remote = a.remote
    a.close()
    a = system.replica(tmp_path/'a.sqlite', remote)

    class OriginAwareEngine(ProtocolEngine):
        async def health(self):
            return {**await super().health(), 'origin_aware': True}

        async def prepare(self, source, origin=None):
            assert origin is None
            return await super().prepare(source)

    system.store.memory_engine = OriginAwareEngine()
    await asyncio.to_thread(a.connect)
    assert a._state()['origin_aware'] == 1
    retried = a.stage('app', legacy['text'], memory_id=memory_id, op_id=legacy['op_id'],
                      origin='user_prompt')
    assert retried['queued'] is True
    assert retried['origin_conveyed'] is False
    assert a.db.execute('SELECT body FROM outbox').fetchone()[0] == original_body
    wire_requests = []
    original_open = a.remote.http.open

    def capture_wire(request, *args, **kwargs):
        if request.full_url.endswith('/v1/sync/ops'):
            wire_requests.append(request.data)
        return original_open(request, *args, **kwargs)

    a.remote.http.open = capture_wire
    expected_wire = json.dumps({'operations': [legacy], 'checkpoint': a._checkpoint()},
                               ensure_ascii=False, allow_nan=False).encode()
    await cycle(a)
    assert wire_requests == [expected_wire]
    assert a.outcome(legacy['op_id'])['state'] == 'applied'
    assert a.status()['pending'] == []
    saved = a.list_memories()[0]
    assert (saved['text'], saved['revision'], saved['session_id'], saved['source_id']) == (
        legacy['text'], 2, None, None)
    assert local(a) == await durable(system, actor.user_id)
    assert await system.store.pool.fetchval('SELECT count(*) FROM am_collab.memory_jobs') == 2
    assert await system.store.pool.fetchval('SELECT count(*) FROM am_collab.changes') == 2


async def test_legacy_discard_receipt_survives_restart_without_reprocessing(system, tmp_path):
    class DiscardEngine(ProtocolEngine):
        calls = 0

        async def prepare(self, source):
            self.calls += 1
            return {'decision': 'discard', 'passages': []}

    discarded_engine = DiscardEngine()
    system.store.memory_engine = discarded_engine
    a, _, actor = await system.pair(tmp_path)
    original = {'op_id': str(uuid4()), 'memory_id': str(uuid4()), 'project': 'app',
                'kind': 'memory', 'base_revision': 0, 'deleted': False,
                'text': 'synthetic discarded candidate', 'session_id': None, 'source_id': None}
    with a.transaction():
        a.db.execute('INSERT INTO outbox(op_id,memory_id,body) VALUES(?,?,?)',
                     (original['op_id'], original['memory_id'], json.dumps(original)))
    await cycle(a)
    outcome = a.outcome(original['op_id'])
    assert outcome == {'op_id': original['op_id'], 'state': 'discarded', 'reason': 'reason_not_recorded'}
    assert discarded_engine.calls == 1
    remote = a.remote
    a.close()
    a = system.replica(tmp_path/'a.sqlite', remote)
    system.store.memory_engine = ProtocolEngine()
    await asyncio.to_thread(a.connect)
    retried = a.stage('app', original['text'], memory_id=original['memory_id'], op_id=original['op_id'])
    assert retried == {'memory_id': original['memory_id'], 'op_id': original['op_id'],
                       'queued': False, 'state': 'discarded', 'reason': outcome['reason']}
    with pytest.raises(Failure, match='^operation_id_reused$'):
        a.stage('app', 'changed discarded candidate', memory_id=original['memory_id'], op_id=original['op_id'])
    await cycle(a)
    assert a.outcome(original['op_id']) == outcome
    assert a.status()['pending'] == []
    assert await durable(system, actor.user_id) == {}
    assert discarded_engine.calls == 1
    assert sum(event['path'] == '/v1/sync/ops' for event in system.proxy.events) == 1
    assert await system.store.pool.fetchval('SELECT count(*) FROM am_collab.memory_jobs') == 1
    assert await system.store.pool.fetchval('SELECT count(*) FROM am_collab.changes') == 0



async def test_hash_only_legacy_intent_requires_review_without_changing_receipt(system, tmp_path):
    a, _, actor = await system.pair(tmp_path)
    arguments = {'memory_id': str(uuid4()), 'op_id': str(uuid4())}
    a.stage('app', 'legacy applied payload', **arguments)
    await cycle(a)
    outcome = a.outcome(arguments['op_id'])
    before = await durable(system, actor.user_id)
    with a.transaction():
        a.db.execute('CREATE TABLE legacy_operation_intents(op_id TEXT PRIMARY KEY,intent TEXT NOT NULL)')
        a.db.execute('INSERT INTO legacy_operation_intents SELECT op_id,intent FROM operation_intents')
        a.db.execute('DROP TABLE operation_intents')
        a.db.execute('ALTER TABLE legacy_operation_intents RENAME TO operation_intents')
    remote = a.remote
    a.close()
    a = system.replica(tmp_path/'a.sqlite', remote)

    with pytest.raises(Failure, match='^operation_history_requires_review$'):
        a.stage('app', 'legacy applied payload', **arguments)

    assert a.outcome(arguments['op_id']) == outcome == {
        'op_id': arguments['op_id'], 'state': 'applied', 'reason': None}
    assert a.status()['pending'] == []
    await cycle(a)
    assert await durable(system, actor.user_id) == before
    assert sum(event['path'] == '/v1/sync/ops' for event in system.proxy.events) == 1
    assert await system.store.pool.fetchval('SELECT count(*) FROM am_collab.memory_jobs') == 1
    assert await system.store.pool.fetchval('SELECT count(*) FROM am_collab.changes') == 1


async def test_conflict_is_visible_without_blocking_unrelated_upload_or_download(system, tmp_path):
    a, b, actor = await system.pair(tmp_path)
    mid = a.stage('app', 'original')['memory_id']
    await cycle(a)
    await cycle(b)
    a.stage('app', 'winner-a', memory_id=mid)
    b.stage('app', 'offline-b', memory_id=mid)
    outgoing = b.stage('app', 'independent-b')['memory_id']
    await cycle(a)
    incoming = a.stage('app', 'independent-a')['memory_id']
    await cycle(a)
    for _ in range(3):
        result = await cycle(b)
        assert result['state'] == 'needs_review'
    assert result['pending'][0]['memory_id'] == mid
    assert result['pending'][0]['error'] == 'revision_conflict'
    assert {outgoing, incoming} <= set(local(b))
    assert {outgoing, incoming} <= set(await durable(system, actor.user_id))
    assert local(b)[mid]['text'] == 'winner-a'
    await asyncio.to_thread(b.resolve, mid, 'local')
    await cycle(b)
    await cycle(a)
    assert local(a) == local(b) == await durable(system, actor.user_id)
    assert local(a)[mid]['text'] == 'offline-b'


def pg(command, *args):
    if not (PG/command).exists():
        pytest.skip('Native PostgreSQL tools are required for real backup/restore')
    return subprocess.run([str(PG/command), '--dbname', DSN, *args], check=True, capture_output=True)


@pytest.mark.parametrize('mode', ['low', 'equal', 'higher', 'pending_write'])
async def test_real_restore_with_reused_revision_and_regrown_cursor_requires_recovery(system, tmp_path, mode):
    a, b, actor = await system.pair(tmp_path)
    mid = a.stage('app', 'backup-v1')['memory_id']
    await cycle(a)
    await cycle(b)
    dump = tmp_path/'synthetic.dump'
    await asyncio.to_thread(pg, 'pg_dump', '-Fc', '-f', str(dump))
    a.stage('app', 'pre-restore-v2', memory_id=mid)
    await cycle(a)
    await cycle(b)
    assert b._state()['cursor'] == 2
    await system.stop_server()
    await asyncio.to_thread(pg, 'pg_restore', '--clean', '--if-exists', '--no-owner', str(dump))
    await system.start()
    if mode in {'equal', 'higher'}:
        c = system.replica(tmp_path/'fresh.sqlite', a.remote)
        await cycle(c)
        c.stage('app', 'restored-branch-v2', memory_id=mid)
        await cycle(c)
        if mode == 'higher':
            c.stage('app', 'cursor crosses previous head')
            await cycle(c)
    if mode == 'pending_write':
        b.stage('app', 'must not erase restore refusal')
    before = local(b)
    with pytest.raises(Failure, match='server_history_changed'):
        await cycle(b)
    assert local(b) == before
    assert all(r['text'] != 'must not erase restore refusal' for r in (await durable(system, actor.user_id)).values())
    result = await asyncio.to_thread(b.recover)
    assert result['recovered']
    assert local(b) == await durable(system, actor.user_id)
    archive = json.loads(b.db.execute('SELECT body FROM recovery_archive WHERE id=?', (result['archive_id'],)).fetchone()[0])
    assert next(r for r in archive['memories'] if r['id'] == mid)['text'] == 'pre-restore-v2'
    if mode == 'pending_write':
        assert result['pending'][0]['status'] == 'needs_review'
        await asyncio.to_thread(b.resolve, result['pending'][0]['memory_id'], 'local')
        await cycle(b)
    await cycle(b)
    assert local(b) == await durable(system, actor.user_id)
    record('restore_'+mode, {'blocked_before_push': True, 'archive_preserved': True, 'recovered': True,
                            'server': await durable(system, actor.user_id), 'client': local(b)})


async def test_checkpoint_rechecks_history_inside_push_transaction(system, tmp_path):
    a, b, actor = await system.pair(tmp_path)
    a.stage('app', 'one')
    await cycle(a)
    await cycle(b)
    pending = b.stage('app', 'after preflight')
    original = b.remote.request
    async def rotate():
        # Fault injection isolates an epoch change between preflight and POST.
        # The operator command also revokes keys, tested separately below.
        await system.store.pool.execute('UPDATE am_collab.installation SET sync_epoch=$1', uuid4())
    loop = asyncio.get_running_loop()
    def changing(path, value=None, **kwargs):
        if path == '/v1/sync/ops':
            asyncio.run_coroutine_threadsafe(rotate(), loop).result(10)
        return original(path, value, **kwargs)
    b.remote.request = changing
    with pytest.raises(Failure, match='server_history_changed'):
        await cycle(b)
    assert len(await durable(system, actor.user_id)) == 1
    assert b.status()['pending'][0]['op_id'] == pending['op_id']


async def test_device_management_is_separate_inventory_and_tree_revocation(system, tmp_path):
    remote, owner = await system.account()
    child = await req(remote, '/v1/devices', {'name': 'PC B', 'writable': True})
    writer = Remote(remote.url, child['token'])
    for method, path, body in [('GET', '/v1/devices', None), ('POST', '/v1/devices', {'name': 'illicit'}),
                              ('DELETE', '/v1/devices/'+child['credential_id'], None)]:
        with pytest.raises(Failure, match='key_manager_required'):
            await req(writer, path, body, method)
    inventory = await req(remote, '/v1/devices')
    assert len(inventory['devices']) == 2
    assert all('digest' not in row and 'token' not in row for row in inventory['devices'])
    # Cascade all children when revoking the manager, even when no child ID was retained.
    await req(remote, '/v1/devices/'+str(owner.credential_id), method='DELETE')
    for key in [remote, writer]:
        with pytest.raises(Failure, match='unauthorized'):
            await req(key, '/v1/me')
    replacement = await system.store.recovery_manager(owner.user_id)
    assert (await req(Remote(remote.url, replacement['token']), '/v1/me'))['manage_keys']


async def test_corrupt_change_page_rolls_back_projection_and_cursor(system, tmp_path):
    a, b, _ = await system.pair(tmp_path)
    a.stage('app', 'one')
    await cycle(a)
    original = b.remote.request
    def corrupt(path, *args, **kwargs):
        page = original(path, *args, **kwargs)
        if path.startswith('/v1/sync/changes'):
            page['cursor'] += 1
        return page
    b.remote.request = corrupt
    with pytest.raises(Failure, match='invalid_sync_page'):
        await cycle(b)
    assert local(b) == {}
    assert b._state()['cursor'] == 0
    assert b.db.execute('SELECT count(*) FROM receipts').fetchone()[0] == 0


async def test_online_partial_edit_preserves_session_and_source_attribution(system, tmp_path):
    a, b, _ = await system.pair(tmp_path)
    mid = a.stage('app', 'summary before edit', kind='summary', session_id='session-a', source_id='source-a')['memory_id']
    await cycle(a)
    await req(a.remote, '/v1/sync/ops', {'operations': [{'op_id': str(uuid4()), 'memory_id': mid,
        'base_revision': 1, 'project': 'app', 'kind': 'summary', 'text': 'edited summary'}]})
    await cycle(b)
    value = b.list_memories()[0]
    assert (value['text'], value['session_id'], value['source_id']) == ('edited summary', 'session-a', 'source-a')


async def test_read_only_device_refuses_local_enqueue(system, tmp_path):
    remote, _ = await system.account()
    key = await req(remote, '/v1/devices', {'name': 'readonly', 'writable': False})
    replica = system.replica(tmp_path/'read.sqlite', Remote(remote.url, key['token']))
    await cycle(replica)
    with pytest.raises(Failure, match='read_only_credential'):
        replica.stage('app', 'must not queue')
    assert replica.status()['pending'] == []


async def test_operator_restore_epoch_invalidates_all_old_credentials(system):
    remote, actor = await system.account()
    child = await req(remote, '/v1/devices', {'name': 'PC'})
    before = await req(remote, '/v1/me')
    after = await system.store.rotate_epoch()
    assert before['epoch'] != after['epoch']
    for key in [remote.token, child['token']]:
        with pytest.raises(Failure, match='unauthorized'):
            await req(Remote(remote.url, key), '/v1/me')
    fresh = await system.store.recovery_manager(actor.user_id)
    assert (await req(Remote(remote.url, fresh['token']), '/v1/me'))['user_id'] == str(actor.user_id)


async def test_nul_input_rejected_and_legacy_bad_item_does_not_block_others(system, tmp_path):
    from pydantic import ValidationError
    a, b, actor = await system.pair(tmp_path)
    with pytest.raises(ValidationError):
        a.stage('app', 'a\x00b')
    assert not a.status()['pending']
    legacy = {'op_id': str(uuid4()), 'memory_id': str(uuid4()), 'project': 'app',
              'kind': 'memory', 'base_revision': 0, 'deleted': False, 'text': 'legacy\x00bad'}
    with a.transaction():
        a.db.execute('INSERT INTO outbox(op_id,memory_id,body) VALUES(?,?,?)',
                     (legacy['op_id'], legacy['memory_id'], json.dumps(legacy)))
    good = a.stage('app', 'independent valid memory')
    result = await cycle(a)
    await cycle(b)
    assert result['state'] == 'needs_review'
    assert result['pending'][0]['error'] == 'invalid_request'
    assert set(await durable(system, actor.user_id)) == {good['memory_id']}
    await asyncio.to_thread(a.resolve, legacy['memory_id'], 'server')
    assert not a.status()['pending']


async def test_operation_id_collision_does_not_wedge_pull_or_resolution(system, tmp_path):
    a, b, actor = await system.pair(tmp_path)
    shared_id = str(uuid4())
    first = a.stage('app', 'first intent', op_id=shared_id)
    await cycle(a)
    second = b.stage('app', 'different intent', op_id=shared_id)
    independent = b.stage('app', 'independent intent')
    result = await cycle(b)
    assert result['pending'][0]['error'] == 'operation_id_reused'
    collision = {'op_id': shared_id, 'state': 'needs_review', 'reason': 'operation_id_reused'}
    assert b.outcome(shared_id) == collision
    assert result['outcomes'] == [{'op_id': independent['op_id'], 'state': 'applied', 'reason': None}]
    remote = b.remote
    b.close()
    b = system.replica(tmp_path/'b.sqlite', remote)
    with pytest.raises(Failure, match='^operation_id_reused$'):
        b.stage('app', 'different intent', memory_id=second['memory_id'], op_id=shared_id)
    assert b.outcome(shared_id) == collision
    assert {first['memory_id'], independent['memory_id']} <= set(local(b))
    await asyncio.to_thread(b.resolve, second['memory_id'], 'local')
    await cycle(b)
    await cycle(a)
    assert len(local(a)) == 3
    assert local(a) == local(b) == await durable(system, actor.user_id)


async def test_healthy_recovery_does_not_demote_pending_or_make_archive(system, tmp_path):
    a, _, _ = await system.pair(tmp_path)
    pending = a.stage('app', 'healthy pending intent')
    result = await asyncio.to_thread(a.recover)
    assert result['recovered'] is False
    assert a.status()['pending'][0]['op_id'] == pending['op_id']
    assert a.status()['pending'][0]['status'] == 'pending'
    assert a.db.execute('SELECT count(*) FROM recovery_archive').fetchone()[0] == 0


async def test_lost_worker_lease_cannot_commit_old_projection_page(system, tmp_path):
    import time
    a, b, _ = await system.pair(tmp_path)
    a.stage('app', 'must not project under a stale owner')
    await cycle(a)
    owner = b._claim()
    original = b.remote.request
    def steal_after_network(path, *args, **kwargs):
        page = original(path, *args, **kwargs)
        if path.startswith('/v1/sync/changes'):
            # Independent SQLite connection simulates another host reclaiming an
            # expired worker while the first host was suspended after its read.
            import sqlite3
            with sqlite3.connect(b.path) as independent:
                independent.execute('UPDATE worker SET owner=?,expires=? WHERE id=1', ('other-owner', time.time()+90))
        return page
    b.remote.request = steal_after_network
    with pytest.raises(Failure, match='replica_worker_lost'):
        await asyncio.to_thread(b._pull, owner)
    assert not local(b) and b._state()['cursor'] == 0
