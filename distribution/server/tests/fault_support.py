import asyncio
import hashlib
import http.client
import json
import os
import socket
import sqlite3
import threading
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
import uvicorn

from agents_memory_collab.client import Remote, Replica
from agents_memory_collab.embedding import E5
from agents_memory_collab.store import Store
from agents_memory_collab.web import create_app

ROOT = Path(os.environ.get('AM_COLLAB_EVIDENCE', '/tmp/agents-memory-test-evidence'))
ROOT.mkdir(parents=True, exist_ok=True)
PG = Path(os.environ.get('AUDIT_PG_BIN', '/workspace/work/native-pg/e2e/runtime/database/18.6.1-vector0.8.7/bin'))
DSN = os.environ.get('AM_COLLAB_TEST_DSN')


def record(name, data):
    (ROOT / (name + '.json')).write_text(json.dumps(data, indent=2, default=str))


def logical(rows):
    return {str(r['id']): {k: r[k] for k in ('project', 'kind', 'text', 'deleted', 'revision')} for r in rows}


def local(replica):
    return logical([dict(r) for r in replica.db.execute('SELECT * FROM memories')])


async def durable(system, uid):
    rows = await system.store.pool.fetch('SELECT id,project,kind,text,deleted,revision FROM am_collab.memories WHERE user_id=$1', uid)
    return logical(rows)


class WireProxy:
    """Actual socket proxy: drop ACK only after receiving committed backend response."""
    def __init__(self, upstream):
        self.upstream = upstream
        self.drop_next_push = False
        self.events = []
        self.hold_identity = None
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def route(self):
                if self.path == '/v1/me' and proxy.hold_identity is not None:
                    proxy.hold_identity.wait(20)
                raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                headers = {k: v for k, v in self.headers.items() if k.lower() not in {'host', 'connection', 'content-length'}}
                headers['Host'] = proxy.upstream
                conn = http.client.HTTPConnection(proxy.upstream, timeout=45)
                conn.request(self.command, self.path, raw or None, headers)
                res = conn.getresponse()
                body = res.read()
                try:
                    req_json = json.loads(raw) if raw else {}
                    payload = json.loads(body)
                except ValueError:
                    req_json, payload = {}, {}
                event = {'method': self.command, 'path': self.path, 'status': res.status,
                         'request_sha256': hashlib.sha256(raw).hexdigest(),
                         'operations': [{k: op.get(k) for k in ('op_id', 'memory_id', 'base_revision', 'project', 'kind', 'deleted')} for op in req_json.get('operations', [])],
                         'acked': payload.get('acked'), 'cursor': payload.get('cursor'), 'head': payload.get('head'),
                         'delivered': True}
                conn.close()
                if proxy.drop_next_push and self.path == '/v1/sync/ops' and res.status == 200:
                    proxy.drop_next_push = False
                    event['delivered'] = False
                    proxy.events.append(event)
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return
                proxy.events.append(event)
                self.send_response(res.status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST = do_PUT = do_DELETE = route

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class System:
    def __init__(self, embedder, dsn=DSN):
        self.embedder, self.dsn = embedder, dsn
        self.proxy = None
        self.replicas = []

    async def start(self):
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        self.port = sock.getsockname()[1]
        sock.close()
        self.url = f'http://127.0.0.1:{self.port}'
        self.store = Store(self.dsn, self.embedder)
        self.server = uvicorn.Server(uvicorn.Config(create_app(self.store, self.url), host='127.0.0.1', port=self.port, log_level='error', access_log=False))
        self.task = asyncio.create_task(self.server.serve())
        for _ in range(200):
            if self.server.started:
                break
            if self.task.done():
                await self.task
                raise RuntimeError('server exited')
            await asyncio.sleep(.025)
        assert self.server.started
        if self.proxy:
            self.proxy.upstream = f'127.0.0.1:{self.port}'
        else:
            self.proxy = WireProxy(f'127.0.0.1:{self.port}')

    async def stop_server(self):
        self.server.should_exit = True
        await asyncio.wait_for(self.task, 15)

    async def close(self):
        for replica in self.replicas:
            with suppress(sqlite3.ProgrammingError):
                replica.close()
        await asyncio.to_thread(self.proxy.close)
        if not self.task.done():
            await self.stop_server()

    async def account(self, name='Synthetic Alice'):
        key = await self.store.create_account(name)
        actor = await self.store.authenticate(key['token'])
        return Remote(self.proxy.url, key['token']), actor

    def replica(self, path, remote):
        r = Replica(path, remote)
        self.replicas.append(r)
        return r

    async def pair(self, path):
        remote, actor = await self.account()
        device = await self.store.create_device(actor, 'Synthetic PC B', True)
        a = self.replica(path/'a.sqlite', remote)
        b = self.replica(path/'b.sqlite', Remote(self.proxy.url, device['token']))
        await asyncio.to_thread(a.connect)
        await asyncio.to_thread(b.connect)
        return a, b, actor


async def req(remote, path, value=None, method=None):
    return await asyncio.to_thread(remote.request, path, value, method=method)


async def cycle(replica, **kwargs):
    return await asyncio.to_thread(replica.cycle, **kwargs)



@pytest_asyncio.fixture
async def system(request):
    if not DSN:
        pytest.skip('Requires an isolated PostgreSQL database')
    expected = os.environ.get('AM_COLLAB_TEST_DATA_DIR')
    if not expected:
        pytest.skip('Set AM_COLLAB_TEST_DATA_DIR to authorize isolated schema replacement')
    conn = await asyncpg.connect(DSN)
    assert Path(await conn.fetchval('SHOW data_directory')).resolve() == Path(expected).resolve()
    await conn.execute('DROP SCHEMA IF EXISTS am_collab CASCADE')
    await conn.close()
    embedder = None
    if directory := os.environ.get('AM_COLLAB_TEST_E5'):
        embedder = E5(Path(directory), Path(os.environ['AM_COLLAB_TEST_E5_MANIFEST']))
    value = System(embedder)
    await value.start()
    try:
        yield value
    finally:
        record(request.node.name.replace('/', '_')+'_wire', value.proxy.events)
        await value.close()
