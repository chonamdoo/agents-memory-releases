import json
import sys
from types import SimpleNamespace
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from agents_memory_collab.client import Replica
from agents_memory_collab.models import Failure, Operation
from agents_memory_collab.protocol import operation_digest
from agents_memory_collab.store import Actor, Store


SECRET = "synthetic-only-" + "Q7" * 18
SOURCES = [
    "sk-" + "Q7" * 24,
    "api key: " + SECRET,
    "credential=" + SECRET,
    "인증 정보: " + SECRET,
    json.dumps(json.dumps({"source": {"secret key": SECRET}})),
]
SAFE = [
    "Never retain API keys, credentials or passwords.",
    "api key: ${API_KEY}",
    "인증 정보: ${AUTH_INFO}",
    json.dumps({"source": {"api_key": "process.env.API_KEY"}}),
]


@pytest.fixture
def replica(tmp_path):
    remote = SimpleNamespace(url="https://synthetic.invalid", token="amc_synthetic_nonfunctional")
    remote.request = lambda path: {
        "user_id": str(uuid4()), "installation_id": str(uuid4()), "epoch": str(uuid4()),
        "writable": True, "memory": {"ready": True, "contract": "agents-memory-grounded-v1"},
    }
    value = Replica(tmp_path / "replica.db", remote)
    value.connect()
    try:
        yield value
    finally:
        value.close()


@pytest.mark.parametrize("text", SOURCES)
def test_stage_refuses_before_outbox_without_persisting_failure(replica, text):
    with pytest.raises(Failure, match="memory_source_contains_credentials"):
        replica.stage("synthetic-project", text)
    assert replica.db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 0
    assert replica.db.execute("SELECT count(*) FROM receipts").fetchone()[0] == 0
    assert replica.db.execute("SELECT count(*) FROM memories").fetchone()[0] == 0


@pytest.mark.parametrize("text", SAFE)
def test_stage_preserves_source_and_idempotent_digest(replica, text):
    mid, oid = uuid4(), uuid4()
    replica.stage("synthetic-project", text, memory_id=mid, op_id=oid)
    before = replica.db.execute("SELECT body FROM outbox").fetchone()[0]
    replica.stage("synthetic-project", text, memory_id=mid, op_id=oid)
    assert replica.db.execute("SELECT body FROM outbox").fetchone()[0] == before
    assert json.loads(before)["text"] == text


def test_stage_screens_serialized_source_reference(replica):
    with pytest.raises(Failure, match="memory_source_contains_credentials"):
        replica.stage("synthetic-project", "Ordinary safe source", source_id="sk-" + "Q7" * 24)
    assert replica.db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 0


def test_stage_missing_guard_is_outage_not_discard(replica, monkeypatch):
    monkeypatch.setitem(sys.modules, "agents_memory.capture_guard", None)
    with pytest.raises(Failure, match="memory_source_guard_unavailable"):
        replica.stage("synthetic-project", "Ordinary safe source")
    assert replica.db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 0


def test_terminal_stage_retry_keeps_outcome_when_guard_unavailable(replica, monkeypatch):
    mid, oid = uuid4(), uuid4()
    replica.stage("synthetic-project", SAFE[0], memory_id=mid, op_id=oid)
    body = json.loads(replica.db.execute("SELECT body FROM outbox").fetchone()[0])
    fingerprint = operation_digest(body)
    replica.db.execute("DELETE FROM outbox")
    replica.db.execute("INSERT INTO receipts(op_id,digest,outcome,reason) VALUES(?,?,?,?)",
                       (str(oid), fingerprint, "discarded", "judge_not_durable"))
    monkeypatch.setitem(sys.modules, "agents_memory.capture_guard", None)
    result = replica.stage("synthetic-project", SAFE[0], memory_id=mid, op_id=oid)
    assert result["queued"] is False
    assert result["state"] == "discarded"
    assert result["reason"] == "judge_not_durable"
    assert replica.db.execute("SELECT digest FROM receipts").fetchone()[0] == fingerprint


def test_stage_invalid_guard_result_fails_closed(replica, monkeypatch):
    from agents_memory import capture_guard
    monkeypatch.setattr(capture_guard, "contains_source_secret", lambda text: None)
    with pytest.raises(Failure, match="memory_source_guard_unavailable"):
        replica.stage("synthetic-project", SAFE[0])
    assert replica.db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 0


class AdmissionPool:
    def __init__(self, prior=None):
        self.prior = prior
        self.writes = []

    async def fetchrow(self, sql, *args):
        return self.prior if "memory_jobs" in sql else None

    async def fetchval(self, sql, *args):
        if "sync_epoch" in sql:
            return "synthetic-epoch"
        return 1

    async def execute(self, sql, *args):
        self.writes.append((sql, args))
        raise AssertionError("Admission must not persist invalid source")


def boundary(prior=None):
    store = Store("unused-synthetic-dsn", memory_engine=object())
    store.pool = AdmissionPool(prior)
    calls = []

    async def process(actor, op, checkpoint):
        calls.append(op)
        return {"acked": [{"op_id": str(op.op_id), "digest": operation_digest(op.model_dump(mode="json"))}]}

    store._process = process
    actor = Actor(uuid4(), uuid4(), uuid4(), True)
    return store, actor, calls


def operation(text):
    return Operation(op_id=uuid4(), memory_id=uuid4(), project="synthetic-project", text=text)


@pytest.mark.parametrize("text", SOURCES)
async def test_server_refuses_batch_before_any_raw_job_or_provider(text):
    store, actor, calls = boundary()
    with pytest.raises(Failure, match="memory_source_contains_credentials"):
        await store.push(actor, [operation(SAFE[0]), operation(text)])
    assert calls == []
    assert store.pool.writes == []


@pytest.mark.parametrize("text", SAFE)
async def test_server_safe_sources_keep_original_digest(text):
    store, actor, calls = boundary()
    op = operation(text)
    result = await store.push(actor, [op])
    assert calls == [op]
    assert result["acked"][0]["digest"] == operation_digest(op.model_dump(mode="json"))


async def test_server_missing_guard_fails_before_processing(monkeypatch):
    store, actor, calls = boundary()
    monkeypatch.setitem(sys.modules, "agents_memory.capture_guard", None)
    with pytest.raises(Failure, match="memory_source_guard_unavailable"):
        await store.push(actor, [operation(SAFE[0])])
    assert calls == []
    assert store.pool.writes == []


async def test_server_terminal_retry_keeps_digest_without_new_guard(monkeypatch):
    op = operation(SAFE[0])
    fingerprint = operation_digest(op.model_dump(mode="json"))
    store, actor, calls = boundary({"fingerprint": fingerprint, "stage": "ready", "prepared": None})
    monkeypatch.setitem(sys.modules, "agents_memory.capture_guard", None)
    result = await store.push(actor, [op])
    assert result["acked"] == [{"op_id": str(op.op_id), "digest": fingerprint}]
    assert calls == [op]
    assert store.pool.writes == []


@pytest.mark.parametrize("text", SOURCES)
async def test_last_server_boundary_refuses_before_job_insert_and_judge(text):
    class LockedPool(AdmissionPool):
        @asynccontextmanager
        async def acquire(self):
            yield self

        async def execute(self, sql, *args):
            if "pg_advisory_" not in sql:
                await super().execute(sql, *args)

    store = Store("unused-synthetic-dsn", memory_engine=object())
    store.pool = LockedPool()
    actor = Actor(uuid4(), uuid4(), uuid4(), True)
    with pytest.raises(Failure, match="memory_source_contains_credentials"):
        await store._process(actor, operation(text), None)
    assert store.pool.writes == []
