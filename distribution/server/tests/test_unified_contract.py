"""Real Hindsight / PostgreSQL contract checks, isolated synthetic data only.

AM_UNIFIED_TEST_RECEIPT must name a runtime created by the accompanying harness.
The private processor must be on PYTHONPATH; it is not redistributed here.
"""
import asyncio
import json
import os
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
import uvicorn
from agents_memory_collab.client import Remote, Replica
from agents_memory_collab.memory_engine import HindsightEngine
from agents_memory_collab.models import Failure, Invite, Operation, ShareMapping
from agents_memory_collab.store import Store
from agents_memory_collab.web import create_app
from hypothesis import given, settings
from hypothesis import strategies as st

pytestmark = pytest.mark.skipif(not os.environ.get("AM_UNIFIED_TEST_RECEIPT"), reason="Requires explicit isolated real-Hindsight runtime")


class TypedJudge:
    """Scripted probability answers; production admission/extraction code runs unchanged."""
    def __init__(self):
        self.calls = 0
        self.fail = False

    def system_one(self, state, questions, **kwargs):
        from agents_memory.jev import ProviderFailure, ProviderResult
        self.calls += 1
        if self.fail:
            raise ProviderFailure("transport")
        answers = {}
        for name in questions:
            i = int(name.rsplit("_", 1)[1])
            text = state["items"][i]["text"]
            keep = not text.startswith(("Thanks", "discard"))
            answers[name] = {"type": "noul", "noul": float(keep) if name.startswith("remember") else 0.0}
        return ProviderResult("synthetic-typed-judge", answers, 0)


def runtime():
    receipt = json.loads(Path(os.environ["AM_UNIFIED_TEST_RECEIPT"]).read_text())
    assert receipt["synthetic_only"] is True
    return receipt


def engine(judge=None):
    from agents_memory.memory_processor import GroundedProcessor
    return HindsightEngine(runtime()["hindsight_url"], GroundedProcessor(judge or TypedJudge()))


@pytest_asyncio.fixture
async def store():
    db = Store(runtime()["dsn"], memory_engine=engine())
    await db.open()
    assert Path(await db.pool.fetchval("SHOW data_directory")).resolve() == Path(runtime()["pg_data"]).resolve()
    yield db
    await db.close()


async def account(store):
    connection = await store.create_account("Synthetic account")
    return connection, await store.authenticate(connection["token"])


def op(text="The synthetic backend uses PostgreSQL 18.", **kw):
    return Operation(op_id=uuid4(), memory_id=uuid4(), project="synthetic-app", text=text, **kw)


@asynccontextmanager
async def server():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    store = Store(runtime()["dsn"], memory_engine=engine())
    url = f"http://127.0.0.1:{port}"
    host = uvicorn.Server(uvicorn.Config(create_app(store, url), host="127.0.0.1", port=port, access_log=False, log_level="error"))
    task = asyncio.create_task(host.serve())
    try:
        for _ in range(400):
            if host.started:
                break
            if task.done():
                await task
            await asyncio.sleep(.025)
        assert host.started
        yield store, url
    finally:
        host.should_exit = True
        await asyncio.wait_for(task, 20)


async def test_fail_closed_without_engine_and_legacy_data_preserved(store):
    _, actor = await account(store)
    store.memory_engine = None
    assert (await store.memory_status())["ready"] is False
    with pytest.raises(Failure, match="memory_engine_unconfigured"):
        await store.push(actor, [op()])
    assert await store.pool.fetchval("SELECT count(*) FROM am_collab.memories WHERE user_id=$1", actor.user_id) == 0


@pytest.mark.parametrize("kind", ["memory", "summary", "prompt"])
async def test_same_processor_preserves_grounded_passages_provenance_and_discard(store, kind):
    _, actor = await account(store)
    if kind == "prompt":
        await store.preferences(actor, True)
    original = op("The synthetic backend uses PostgreSQL 18.\nThanks for the update.", kind=kind, session_id="session-A", source_id="source-A")
    first = await store.push(actor, [original])
    assert await store.push(actor, [original]) == first
    row = await store.pool.fetchrow("SELECT * FROM am_collab.memories WHERE user_id=$1 AND id=$2", actor.user_id, original.memory_id)
    assert row["text"] == "The synthetic backend uses PostgreSQL 18."
    assert row["session_id"] == "session-A" and row["source_id"] == "source-A"
    assert await store.memory_engine.read(row["engine_bank"], row["engine_document"]) == row["text"]
    document = await store.memory_engine.request("/v1/default/banks/" + row["engine_bank"] + "/documents/" + row["engine_document"])
    assert document["document_metadata"]["source_id"] == "source-A"
    assert document["document_metadata"]["session_id"] == "session-A"
    job = await store.pool.fetchrow("SELECT * FROM am_collab.memory_jobs WHERE user_id=$1 AND op_id=$2", actor.user_id, original.op_id)
    assert json.loads(job["original"])["text"] == original.text
    assert job["stage"] == "ready"
    rejected_edit = original.model_copy(update={"op_id": uuid4(), "base_revision": 1, "text": "discard this passing message"})
    rejected = await store.push(actor, [rejected_edit])
    assert rejected["discarded"][0]["state"] == "discarded"
    assert await store.push(actor, [rejected_edit]) == rejected
    assert await store.pool.fetchval("SELECT text FROM am_collab.memories WHERE user_id=$1 AND id=$2", actor.user_id, original.memory_id) == row["text"]
    assert not (await store.search(actor, "Thanks"))["memories"] if kind == "prompt" else True


async def test_provider_failure_then_restart_retry_does_not_publish_raw(store):
    _, actor = await account(store)
    item = op()
    judge = store.memory_engine.processor.client
    judge.fail = True
    with pytest.raises(Failure, match="memory_provider_retryable"):
        await store.push(actor, [item])
    assert await store.pool.fetchval("SELECT stage FROM am_collab.memory_jobs WHERE user_id=$1 AND op_id=$2", actor.user_id, item.op_id) == "received"
    assert (await store.search(actor, "PostgreSQL"))["memories"] == []
    # New Store and processor instance: no reliance on an in-memory success flag.
    restarted = Store(runtime()["dsn"], memory_engine=engine())
    await restarted.open()
    try:
        await restarted.push(actor, [item])
        assert len((await restarted.search(actor, "PostgreSQL"))["memories"]) == 1
    finally:
        await restarted.close()


async def test_hindsight_ack_loss_reuses_verified_document_and_prepared_result(store):
    _, actor = await account(store)
    item = op()
    index = store.memory_engine.index
    async def lost(*args):
        await index(*args)
        raise Failure(503, "synthetic_ack_loss")
    store.memory_engine.index = lost
    with pytest.raises(Failure, match="synthetic_ack_loss"):
        await store.push(actor, [item])
    assert (await store.search(actor, "PostgreSQL"))["memories"] == []
    store.memory_engine.index = index
    await store.push(actor, [item])
    assert store.memory_engine.processor.client.calls == 1
    assert len((await store.changes(actor, 0))["changes"]) == 1


async def test_legacy_migration_is_explicit_preserves_identity_and_retries_after_crash(store):
    key, actor = await account(store)
    source = op("The synthetic backend uses PostgreSQL 18.\nThanks for the update.", session_id="old-session", source_id="old-source")
    # Seed the old raw projection and log without using the new public write path.
    await store._commit(actor, [source])
    await store.pool.execute("UPDATE am_collab.memories SET processing_state='legacy_pending' WHERE user_id=$1", actor.user_id)
    plan = await store.legacy_plan(actor)
    assert plan["apply_performed"] is False and len(plan["items"]) == 1
    assert "text" not in plan["items"][0]
    assert (await store.search(actor, "PostgreSQL"))["memories"] == []
    original_index = store.memory_engine.index
    async def crash(*args):
        await original_index(*args)
        raise Failure(503, "synthetic_crash_after_index")
    store.memory_engine.index = crash
    with pytest.raises(Failure, match="synthetic_crash_after_index"):
        await store.reprocess_legacy(actor, source.memory_id)
    assert await store.pool.fetchval("SELECT text FROM am_collab.memories WHERE user_id=$1 AND id=$2", actor.user_id, source.memory_id) == source.text
    assert await store.authenticate(key["token"]) == actor
    restarted = Store(runtime()["dsn"], memory_engine=engine())
    await restarted.open()
    try:
        await restarted.reprocess_legacy(actor, source.memory_id)
        assert restarted.memory_engine.processor.client.calls == 0
        current = await restarted.pool.fetchrow("SELECT * FROM am_collab.memories WHERE user_id=$1 AND id=$2", actor.user_id, source.memory_id)
        assert current["revision"] == 2 and current["text"] == "The synthetic backend uses PostgreSQL 18."
        assert (current["session_id"], current["source_id"]) == ("old-session", "old-source")
        assert (await restarted.reprocess_legacy(actor, source.memory_id))["state"] == "ready"
        assert (await restarted.legacy_plan(actor))["items"] == []
        # Historical source is preserved; physical history erasure is not claimed.
        historical = json.loads(await restarted.pool.fetchval("SELECT body::text FROM am_collab.changes WHERE user_id=$1 AND sequence=1", actor.user_id))
        assert historical["text"] == source.text
    finally:
        await restarted.close()


async def test_backend_configuration_drift_blocks_publication(store):
    _, actor = await account(store)
    item = op()
    bank = store.memory_engine.bank(actor.user_id, item.project)
    await store.memory_engine.request("/v1/default/banks/" + bank, {}, "PUT")
    await store.memory_engine.request("/v1/default/banks/" + bank + "/config", {"updates":{"enable_observations":True}}, "PATCH")
    with pytest.raises(Failure, match="memory_backend_contract_mismatch"):
        await store.push(actor, [item])
    assert (await store.search(actor, "PostgreSQL"))["memories"] == []


@pytest.mark.parametrize("mutation", ["omission", "duplicate", "unauthorized"])
async def test_wire_inspector_detects_intentionally_broken_search(mutation):
    async with server() as (store, url):
        key, actor = await account(store)
        _, outsider = await account(store)
        allowed, forbidden = op(), op("The other synthetic account has a private deployment rule.")
        await store.push(actor, [allowed])
        await store.push(outsider, [forbidden])
        original = store.search
        async def broken(*args, **kwargs):
            value = await original(*args, **kwargs)
            if mutation == "omission":
                value["memories"] = []
            elif mutation == "duplicate":
                value["memories"] *= 2
            else:
                value["memories"].append({"id": str(forbidden.memory_id), "text": forbidden.text})
            return value
        store.search = broken
        actual = await asyncio.to_thread(Remote(url, key["token"]).request, "/v1/recall", {"query":"PostgreSQL"})
        rows = await store.pool.fetch("SELECT id,text,deleted FROM am_collab.memories WHERE user_id=$1", actor.user_id)
        persisted = {str(row["id"]): {"text":row["text"],"deleted":row["deleted"]} for row in rows}
        expected = {str(allowed.memory_id): {"text":allowed.text,"deleted":False}}
        with pytest.raises(AssertionError):
            inspect_state(expected, persisted, [{"id":str(row["id"])} for row in actual["memories"]])


async def test_grounding_guard_rejects_fabricated_or_duplicate_passages():
    class Forged:
        contract = "agents-memory-grounded-v1"
        async def process(self, source):
            return {"contract":self.contract,"decision":"keep","extraction":"source_passages",
                "consolidation":"not_required_no_generated_observations",
                "passages":[{"start":0,"end":5,"text":"forged"}]}
    adapter = HindsightEngine(runtime()["hindsight_url"], Forged())
    with pytest.raises(Failure, match="ungrounded_memory_processing_result"):
        await adapter.prepare("Original synthetic source.")


async def test_processing_does_not_deadlock_when_every_pool_connection_is_occupied(store):
    _, actor = await account(store)
    await store.pool.close()
    store.pool = await asyncpg.create_pool(runtime()["dsn"], min_size=1, max_size=2, command_timeout=10)
    original = store.memory_engine.prepare
    arrived, gate = 0, asyncio.Event()
    async def barrier(source):
        nonlocal arrived
        arrived += 1
        if arrived == 2:
            gate.set()
        await gate.wait()
        return await original(source)
    store.memory_engine.prepare = barrier
    # Both operations own one connection before either can publish. Publication
    # must reuse its owned connection, not wait for a third one from the pool.
    await asyncio.wait_for(asyncio.gather(store.push(actor, [op()]), store.push(actor, [op()])), timeout=5)
    assert (await store.changes(actor, 0))["head"] == 2


async def test_optional_empty_hindsight_metadata_is_not_a_false_index_failure():
    adapter = engine()
    prepared = await adapter.prepare("The synthetic metadata fixture uses PostgreSQL 18.")
    bank = "empty-metadata-" + uuid4().hex
    assert await adapter.index(bank, "synthetic-empty-metadata", prepared) == "The synthetic metadata fixture uses PostgreSQL 18."
    assert await adapter.index(bank, "synthetic-empty-metadata", prepared) == "The synthetic metadata fixture uses PostgreSQL 18."


async def test_backend_hit_is_not_lost_behind_unrelated_projection_rows(store):
    _, actor = await account(store)
    item = op()
    await store.push(actor, [item])
    bank = store.memory_engine.bank(actor.user_id, item.project)
    # Fault fixture: stale projections do not correspond to Hindsight documents.
    # They must never exclude a genuine current backend hit before ranking.
    await store.pool.execute("""INSERT INTO am_collab.memories(user_id,id,project,kind,revision,deleted,text,device_id,
        processing_state,engine_bank,engine_document)
        SELECT $1,gen_random_uuid(),'synthetic-app','memory',1,false,'An unrelated synthetic projection row',$2,
        'ready',$3,'missing-'||n FROM generate_series(1,10001) n""", actor.user_id, actor.device_id, bank)
    result = await store.search(actor, "데이터베이스 저장 엔진 버전", project=item.project)
    assert [row["id"] for row in result["memories"]] == [item.memory_id]


async def test_actual_http_ack_loss_two_sqlite_clients_edit_delete_and_conflict():
    from fault_support import WireProxy
    async with server() as (store, url):
        proxy = WireProxy(url.removeprefix("http://"))
        key, actor = await account(store)
        second = await store.create_device(actor, "Synthetic PC B", True)
        import tempfile
        with tempfile.TemporaryDirectory(prefix="am-unified-") as folder:
            a = Replica(Path(folder)/"a.sqlite", Remote(proxy.url, key["token"]))
            b = Replica(Path(folder)/"b.sqlite", Remote(proxy.url, second["token"]))
            try:
                await asyncio.to_thread(a.connect)
                await asyncio.to_thread(b.connect)
                staged = a.stage("synthetic-app", "The synthetic backend uses PostgreSQL 18.\nThanks for the update.", session_id="session-A", source_id="source-A")
                mid = staged["memory_id"]
                proxy.drop_next_push = True
                with pytest.raises((OSError, ConnectionError)):
                    await asyncio.to_thread(a.cycle)
                await asyncio.to_thread(a.cycle)
                await asyncio.to_thread(b.cycle)
                assert a.status()["pending"] == []
                assert a.list_memories()[0]["text"] == b.list_memories()[0]["text"] == "The synthetic backend uses PostgreSQL 18."
                assert store.memory_engine.processor.client.calls == 1
                a.stage("synthetic-app", "The synthetic backend uses PostgreSQL 19.", memory_id=mid, base_revision=1)
                b.stage("synthetic-app", "The synthetic backend uses PostgreSQL 20.", memory_id=mid, base_revision=1)
                b.stage("synthetic-app", "The independent synthetic module uses Python 3.12.")
                await asyncio.to_thread(a.cycle)
                await asyncio.to_thread(b.cycle)
                assert b.status()["pending"][0]["error"] == "revision_conflict"
                assert len(b.list_memories()) == 2
                assert b.list_memories()[0]["source_id"] is None or b.list_memories()[1]["source_id"] == "source-A"
                await asyncio.to_thread(a.cycle)
                a.stage("synthetic-app", None, memory_id=mid, base_revision=2, deleted=True)
                await asyncio.to_thread(a.cycle)
                await asyncio.to_thread(b.cycle)
                assert all(row["id"] != mid for row in b.list_memories())
                assert all(str(row["id"]) != mid for row in (await store.search(actor, "PostgreSQL"))["memories"])
                rows = await store.pool.fetch("SELECT bank,document FROM am_collab.memory_jobs WHERE user_id=$1 AND original->>'memory_id'=$2 AND stage='ready'", actor.user_id, mid)
                for row in rows:
                    assert await store.memory_engine.read(row["bank"], row["document"]) is None
            finally:
                a.close()
                b.close()
                await asyncio.to_thread(proxy.close)


async def test_private_not_shared_and_new_queries_after_unshare_leave_revoke(store):
    _, owner = await account(store)
    _, reader = await account(store)
    team = UUID((await store.create_team(owner, "Synthetic team"))["id"])
    project = UUID((await store.create_project(owner, team, "Synthetic project"))["id"])
    invitation = await store.invite(owner, team, Invite(projects=[project]))
    await store.accept(reader, invitation["invite"])
    await store.push(owner, [op()])
    assert (await store.search(reader, "PostgreSQL", team=team))["memories"] == []
    await store.sharing(owner, team, [ShareMapping(source_project="synthetic-app", project_id=project)])
    assert len((await store.search(reader, "PostgreSQL", team=team))["memories"]) == 1
    assert len((await store.brief(reader, team, project))["items"]) == 1
    await store.sharing(owner, team, [])
    assert (await store.search(reader, "PostgreSQL", team=team))["memories"] == []
    assert (await store.brief(reader, team, project))["items"] == []
    await store.sharing(owner, team, [ShareMapping(source_project="synthetic-app", project_id=project)])
    await store.remove_member(reader, team)
    with pytest.raises(Failure):
        await store.search(reader, "PostgreSQL", team=team)
    with pytest.raises(Failure):
        await store.brief(reader, team, project)
    await store.revoke_device(owner, owner.credential_id)
    with pytest.raises(Failure, match="unauthorized"):
        await store.search(owner, "PostgreSQL")


def inspect_state(expected, actual, visible):
    assert actual == expected
    assert len(visible) == len({row["id"] for row in visible})
    assert {row["id"] for row in visible} == {k for k,v in expected.items() if not v["deleted"]}


@pytest.mark.parametrize("mutation", ["omission", "duplicate", "unauthorized"])
def test_independent_inspector_rejects_injected_errors(mutation):
    expected = {"allowed": {"text": "Synthetic fact", "deleted": False}}
    actual = dict(expected)
    visible = [{"id": "allowed"}]
    if mutation == "omission":
        actual = {}
    elif mutation == "duplicate":
        visible *= 2
    else:
        visible.append({"id": "forbidden"})
    with pytest.raises(AssertionError):
        inspect_state(expected, actual, visible)


@settings(max_examples=5, deadline=None, derandomize=True)
@given(st.lists(st.sampled_from(["edit", "delete", "discard"]), min_size=1, max_size=5))
async def test_reference_model_over_generated_operation_sequences(actions):
    db = Store(runtime()["dsn"], memory_engine=engine())
    await db.open()
    try:
        _, actor = await account(db)
        item = op()
        expected = {}
        revision = 0
        for action in ["edit", *actions]:
            text = f"The synthetic revision counter is {revision + 1}."
            if action == "discard":
                text = "discard this transient sentence"
            current = item.model_copy(update={"op_id": uuid4(), "base_revision": revision,
                "text": None if action == "delete" else text, "deleted": action == "delete"})
            await db.push(actor, [current])
            if action != "discard":
                revision += 1
                expected[str(item.memory_id)] = {"text": None if action == "delete" else text, "deleted": action == "delete"}
            rows = await db.pool.fetch("SELECT id,text,deleted FROM am_collab.memories WHERE user_id=$1", actor.user_id)
            actual = {str(r["id"]): {"text":r["text"],"deleted":r["deleted"]} for r in rows}
            visible = [{"id":str(r["id"])} for r in (await db.search(actor, "synthetic revision"))["memories"]]
            inspect_state(expected, actual, visible)
    finally:
        await db.close()
