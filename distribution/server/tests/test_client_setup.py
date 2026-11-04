import asyncio
import json
import os
import sys
import tomllib
from argparse import Namespace
from pathlib import Path
from uuid import uuid4

from fault_support import cycle, durable, local
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agents_memory_collab.setup import install, write_private


async def test_setup_all_clients_preserves_configuration_and_device_key_on_update(system, tmp_path):
    remote, actor = await system.account()
    supplied = tmp_path/'operator.connection.json'
    write_private(supplied, json.dumps({'url': remote.url, 'token': remote.token}))
    project = tmp_path/'project'
    project.mkdir()
    (project/'.mcp.json').write_text('{"mcpServers":{"existing":{"command":"keep"}}}')
    args = Namespace(profile='personal', client=['all'], root=tmp_path/'persistent',
                     project=project, project_name='app', url=remote.url, credential_file=supplied, device_name='test PC')
    result = await asyncio.to_thread(install, args)
    assert result['ready']
    config = tmp_path/'persistent/personal/connection.json'
    first = config.read_bytes()
    stored = json.loads(first)
    assert stored['token'] != remote.token
    device = await system.store.authenticate(stored['token'])
    assert device.writable and not device.manage_keys
    assert len((await system.store.list_devices(actor))['devices']) == 2
    await asyncio.to_thread(install, args)
    assert config.read_bytes() == first
    assert len((await system.store.list_devices(actor))['devices']) == 2
    for path in result['config_files']:
        raw = Path(path).read_text()
        assert stored['token'] not in raw and remote.token not in raw
        parsed = tomllib.loads(raw) if path.endswith('.toml') else json.loads(raw)
        server = parsed['mcp_servers' if path.endswith('.toml') else 'mcpServers']['agents-memory-cloud']
        assert server['args'][2] == 'mcp'
        assert '--state' in server['args']
    assert json.loads((project/'.mcp.json').read_text())['mcpServers']['existing']['command'] == 'keep'


def parameters(connection, state):
    return StdioServerParameters(command=sys.executable,
        args=['-m', 'agents_memory_collab.cli', 'mcp', '--connection', str(connection), '--state', str(state), '--project', 'app'],
        env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src')))


async def test_actual_stdio_startup_recall_offline_queue_restart_and_other_pc_apply(system, tmp_path):
    a, b, actor = await system.pair(tmp_path)
    a.stage('app', 'Synthetic PR reviewer rule from previous session')
    await cycle(a)
    connection = tmp_path/'connection.json'
    write_private(connection, json.dumps({'url': a.remote.url, 'token': a.remote.token}))
    a.close()
    state = tmp_path/'a.sqlite'
    intent = {'op_id': str(uuid4()), 'memory_id': str(uuid4()), 'project': 'app', 'text': 'Synthetic offline decision', 'session_id': 'session-test'}
    async with stdio_client(parameters(connection, state)) as (read, write), ClientSession(read, write) as session:
        initialized = await session.initialize()
        # Context is really delivered in initialize, without asking the model to invoke recall first.
        assert 'Synthetic PR reviewer rule' in initialized.instructions
        await system.stop_server()
        result = await session.call_tool('sync_retain', intent)
        assert not result.is_error
        assert json.loads(result.content[0].text)['state'] == 'queued'
        status = json.loads((await session.call_tool('setup_status', {})).content[0].text)
        assert status['replica']['pending'][0]['op_id'] == intent['op_id']
    await system.start()
    async with stdio_client(parameters(connection, state)) as (read, write), ClientSession(read, write) as session:
        initialized = await session.initialize()
        assert 'Synthetic offline decision' in initialized.instructions
        status = json.loads((await session.call_tool('setup_status', {})).content[0].text)
        assert status['ready'] and not status['replica']['pending']
        retry = await session.call_tool('sync_retain', intent)
        assert not retry.is_error and json.loads(retry.content[0].text)['state'] == 'applied'
    await cycle(b)
    assert local(b) == await durable(system, actor.user_id)
    assert len(local(b)) == 2
    assert next(r for r in b.list_memories() if r['id'] == intent['memory_id'])['session_id'] == 'session-test'


async def test_actual_client_installer_and_repeat_install_keeps_settings(system, tmp_path):
    remote, actor = await system.account()
    supplied = tmp_path/'operator.connection.json'
    write_private(supplied, json.dumps({'url': remote.url, 'token': remote.token}))
    project, prefix = tmp_path/'app', tmp_path/'client'
    project.mkdir()
    script = Path(__file__).resolve().parents[1]/'install-client.sh'
    env = dict(os.environ, AM_COLLAB_CLIENT_ROOT=str(prefix), PYTHONDONTWRITEBYTECODE='1')
    # Installed-wheel verification must not accidentally import the source tree.
    env.pop('PYTHONPATH', None)
    command = ['bash', str(script), '--client', 'all', '--project', str(project), '--credential-file', str(supplied)]
    async def run():
        process = await asyncio.create_subprocess_exec(*command, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(process.communicate(), 180)
        assert process.returncode == 0, stderr.decode()[-2000:]
        return json.loads(stdout)
    result = await run()
    assert result['ready']
    saved = (prefix/'personal/connection.json').read_bytes()
    await run()
    assert (prefix/'personal/connection.json').read_bytes() == saved
    assert len((await system.store.list_devices(actor))['devices']) == 2
    # Cloud clients install neither embedding packages nor a local database.
    process = await asyncio.create_subprocess_exec(str(prefix/'venv/bin/python'), '-c',
        'import importlib.util; assert importlib.util.find_spec("onnxruntime") is None; import agents_memory_collab', env=env)
    assert await process.wait() == 0
    config = json.loads((project/'.mcp.json').read_text())['mcpServers']['agents-memory-cloud']
    params = StdioServerParameters(command=config['command'], args=config['args'], env=env)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        initialized = await session.initialize()
        assert initialized.server_info.version == '0.2.1'
        status = await session.call_tool('setup_status', {})
        assert json.loads(status.content[0].text)['ready']


async def test_shared_host_lease_still_delivers_recent_startup_context(system, tmp_path):
    a, _, _ = await system.pair(tmp_path)
    a.stage('app', 'Shared host startup rule')
    await cycle(a)
    owner = a._claim()
    connection = tmp_path/'connection.json'
    write_private(connection, json.dumps({'url': a.remote.url, 'token': a.remote.token}))
    try:
        async with stdio_client(parameters(connection, a.path)) as (read, write), ClientSession(read, write) as session:
            initialized = await session.initialize()
            assert 'Shared host startup rule' in initialized.instructions
            status = json.loads((await session.call_tool('setup_status', {})).content[0].text)
            assert status['ready'] and status['sync']['state'] == 'busy'
    finally:
        a._release(owner)


async def test_silent_network_does_not_delay_mcp_initialize_until_timeout(system, tmp_path):
    import threading
    a, _, _ = await system.pair(tmp_path)
    a.stage('app', 'Cached startup rule while network stalls')
    await cycle(a)
    connection = tmp_path/'connection.json'
    write_private(connection, json.dumps({'url': a.remote.url, 'token': a.remote.token}))
    system.proxy.hold_identity = threading.Event()
    try:
        async with stdio_client(parameters(connection, a.path)) as (read, write), ClientSession(read, write) as session:
            initialized = await asyncio.wait_for(session.initialize(), 5)
            assert 'Cached startup rule' in initialized.instructions
            system.proxy.hold_identity.set()
    finally:
        system.proxy.hold_identity.set()


async def test_explicit_key_replacement_and_restore_recovery_in_setup(system, tmp_path):
    remote, owner = await system.account()
    supplied = tmp_path/'manager.json'
    write_private(supplied, json.dumps({'url': remote.url, 'token': remote.token}))
    project = tmp_path/'app'
    project.mkdir()
    args = Namespace(profile='personal', client=['all'], root=tmp_path/'profiles', project=project,
                     project_name='app', url=remote.url, credential_file=supplied, device_name='PC')
    await asyncio.to_thread(install, args)
    original = (tmp_path/'profiles/personal/connection.json').read_bytes()
    other, _ = await system.account('unrelated')
    write_private(supplied, json.dumps({'url': other.url, 'token': other.token}))
    args.replace_credential = True
    import pytest

    from agents_memory_collab.models import Failure
    with pytest.raises(Failure, match='destination_changed'):
        await asyncio.to_thread(install, args)
    assert (tmp_path/'profiles/personal/connection.json').read_bytes() == original
    await system.store.rotate_epoch()
    recovered = await system.store.recovery_manager(owner.user_id)
    write_private(supplied, json.dumps({'url': remote.url, 'token': recovered['token']}))
    args.recover = True
    result = await asyncio.to_thread(install, args)
    assert result['ready']
    assert (tmp_path/'profiles/personal/connection.json').read_bytes() != original
