import asyncio
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from fault_support import DSN, ROOT, System, cycle, durable, local, record, req
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule
from test_reference_model import Spec

TRACES = []
pytestmark = pytest.mark.skipif(not os.environ.get('AM_COLLAB_TEST_DATA_DIR'), reason='isolated cluster required')


class ReplicaMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        (ROOT/'private').mkdir(mode=0o700, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='state-machine-', dir=ROOT/'private')
        self.model = Spec()
        self.trace = []
        self.call(self.setup())

    def call(self, coroutine):
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result(timeout=60)

    async def setup(self):
        db = await asyncpg.connect(DSN)
        assert Path(await db.fetchval('SHOW data_directory')).resolve() == Path(os.environ['AM_COLLAB_TEST_DATA_DIR']).resolve()
        exists = await db.fetchval("SELECT 1 FROM pg_database WHERE datname='implementation_state'")
        if not exists:
            await db.execute('CREATE DATABASE implementation_state')
        await db.close()
        dsn = DSN.rsplit('/', 1)[0]+'/implementation_state'
        db = await asyncpg.connect(dsn)
        await db.execute('DROP SCHEMA IF EXISTS am_collab CASCADE')
        await db.close()
        self.system = System(None, dsn)
        await self.system.start()
        a, b, self.actor = await self.system.pair(Path(self.temp.name))
        self.clients = [a, b]
        await req(a.remote, '/v1/preferences', {'upload_prompts': True}, 'PUT')

    @rule(device=st.integers(0, 1), kind=st.sampled_from(['memory', 'summary', 'prompt']),
          delete=st.booleans(), edit=st.booleans(), lost_ack=st.booleans(), content=st.text(alphabet='abc 한글Ω', min_size=1, max_size=20).filter(lambda x: bool(x.strip())))
    def write_retry_sync(self, device, kind, delete, edit, lost_ack, content):
        a = self.clients[device]
        candidates = list(self.model.records)
        mid = candidates[0] if edit and candidates else str(uuid4())
        if mid in self.model.records:
            kind = self.model.records[mid]['kind']
        intended = {'memory_id': mid, 'project': 'scope-a', 'kind': kind, 'text': None if delete else content,
                        'deleted': delete, 'base_revision': self.model.records.get(mid, {}).get('revision', 0)}
        # Each generated mutation follows a fully converged base; concurrent branch is tested separately.
        pending = a.stage('scope-a', None if delete else content, memory_id=mid,
                          kind=kind, deleted=delete, allow_prompts=True)
        op = json.loads(a.db.execute('SELECT body FROM outbox WHERE op_id=?', (pending['op_id'],)).fetchone()[0])
        expected = dict(intended, op_id=pending['op_id'])
        assert pending['memory_id'] == mid
        assert {k:v for k,v in op.items() if k not in {'session_id', 'source_id'}} == expected, 'Input meaning changed before durable enqueue'
        self.model.commit(expected)  # Expectations come from generated user intent, not product serialization.
        self.system.proxy.drop_next_push = lost_ack
        if lost_ack:
            try:
                self.call(cycle(a))
            except OSError:
                pass
        self.call(cycle(a))
        self.call(cycle(self.clients[1-device]))
        # Re-deliver same immutable intent: allowed effect remains exactly one.
        self.call(req(a.remote, '/v1/sync/ops', {'operations': [op]}))
        self.trace.append({'action': 'write/delete+retry+sync', 'device': device, 'lost_ack': lost_ack, 'intent': expected})

    @rule(device=st.integers(0, 1))
    def reopen_sqlite(self, device):
        old = self.clients[device]
        remote = old.remote
        old.close()
        self.clients[device] = self.system.replica(Path(self.temp.name)/['a.sqlite', 'b.sqlite'][device], remote)
        self.call(cycle(self.clients[device]))
        self.trace.append({'action': 'reopen+sync', 'device': device})

    @invariant()
    def independently_expected_persistent_state(self):
        self.model.compare(self.call(durable(self.system, self.actor.user_id)))
        for client in self.clients:
            self.model.compare(local(client))
            assert client.db.execute('SELECT count(*) FROM outbox').fetchone()[0] == 0

    def teardown(self):
        TRACES.append(self.trace)
        record('stateful-traces', {'seed_command': next((arg for arg in sys.argv if arg.startswith('--hypothesis-seed=')), 'not specified'), 'max_examples': 20,
            'max_steps': 20, 'model_imports_product': False, 'semantic_embedding': False,
            'real_pgvector_database': True, 'traces': TRACES,
            'scope': 'serial write/delete, replay, lost ACK, two replicas, reopen; not all concurrent histories'})
        self.call(self.system.close())
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()
        self.loop.close()
        self.temp.cleanup()


TestReplicaMachine = ReplicaMachine.TestCase
TestReplicaMachine.settings = settings(max_examples=20, stateful_step_count=20, deadline=None, database=None)
