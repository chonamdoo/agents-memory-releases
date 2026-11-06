from __future__ import annotations

import asyncio
import json
import os
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

import httpx2
import pytest
import pytest_asyncio
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from agents_memory_collab.client import Remote, Replica
from agents_memory_collab.models import Failure, Invite, Operation, ShareMapping
from agents_memory_collab.store import Store
from agents_memory_collab.web import create_app
from engine_double import ProtocolEngine

DSN = os.environ.get("AM_COLLAB_TEST_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="Requires isolated AM_COLLAB_TEST_DSN PostgreSQL/pgvector")


@pytest_asyncio.fixture
async def store():
    expected = os.environ.get("AM_COLLAB_TEST_DATA_DIR")
    if not expected:
        pytest.skip("Requires explicit AM_COLLAB_TEST_DATA_DIR")
    db = Store(DSN, memory_engine=ProtocolEngine())
    await db.open()
    async with db.pool.acquire() as connection:
        assert Path(await connection.fetchval("SHOW data_directory")).resolve() == Path(expected).resolve()
        tables = await connection.fetch("SELECT tablename FROM pg_tables WHERE schemaname='am_collab' AND tablename<>'installation'")
        await connection.execute("TRUNCATE " + ",".join('am_collab."' + row["tablename"] + '"' for row in tables) + " RESTART IDENTITY CASCADE")
    yield db
    await db.close()


async def account(store, name="Alice"):
    connection = await store.create_account(name)
    return connection, await store.authenticate(connection["token"])


def operation(text="Use four reviewers for PRs", project="app", **changes):
    return Operation(op_id=uuid4(), memory_id=uuid4(), project=project, text=text, **changes)


async def test_personal_devices_retry_edit_delete_and_other_account_isolation(store):
    _, alice = await account(store)
    second = await store.create_device(alice, "second PC", True)
    device = await store.authenticate(second["token"])
    _, bob = await account(store, "Bob")
    op = operation()
    first = await store.push(alice, [op])
    assert await store.push(device, [op]) == first
    assert len((await store.changes(device, 0))["changes"]) == 1
    assert (await store.changes(bob, 0))["changes"] == []
    assert (await store.search(bob, "reviewers"))["memories"] == []
    edit = op.model_copy(update={"op_id": uuid4(), "base_revision": 1, "text": "Use five reviewers"})
    await store.push(device, [edit])
    assert (await store.search(alice, "five"))["memories"][0]["revision"] == 2
    deletion = edit.model_copy(update={"op_id": uuid4(), "base_revision": 2, "deleted": True, "text": None})
    await store.push(alice, [deletion])
    assert (await store.search(device, "reviewers"))["memories"] == []
    assert (await store.changes(device, 2))["changes"][0]["text"] is None


async def test_concurrent_writes_commit_order_and_atomic_conflict(store):
    _, actor = await account(store)
    a, b = operation(), operation("Another memory")
    await asyncio.gather(store.push(actor, [a]), store.push(actor, [b]))
    assert [x["sequence"] for x in (await store.changes(actor, 0))["changes"]] == [1, 2]
    with pytest.raises(Failure, match="revision_conflict"):
        await store.push(actor, [operation("must roll back"), a.model_copy(update={"op_id": uuid4()})])
    assert (await store.changes(actor, 0))["head"] == 2
    with pytest.raises(Failure, match="operation_id_reused"):
        await store.push(actor, [a.model_copy(update={"text": "changed retry"})])


async def test_device_revocation_read_scope_and_explicit_prompt_consent(store):
    _, actor = await account(store)
    read = await store.create_device(actor, "read-only", False)
    reader = await store.authenticate(read["token"])
    with pytest.raises(Failure, match="read_only"):
        await store.push(reader, [operation()])
    prompt = operation("raw prompt", kind="prompt")
    with pytest.raises(Failure, match="prompt_upload_requires_explicit_opt_in"):
        await store.push(actor, [prompt])
    await store.preferences(actor, True)
    await store.push(actor, [prompt])
    assert (await store.changes(actor, 0))["changes"][0]["kind"] == "prompt"
    assert (await store.search(actor, "raw"))["memories"] == []
    await store.revoke_device(actor, UUID(read["credential_id"]))
    with pytest.raises(Failure, match="unauthorized"):
        await store.authenticate(read["token"])


async def team_fixture(store):
    _, owner = await account(store)
    _, bob = await account(store, "Bob")
    team = UUID((await store.create_team(owner, "Engineering"))["id"])
    project = UUID((await store.create_project(owner, team, "Trading"))["id"])
    secret_project = UUID((await store.create_project(owner, team, "Private"))["id"])
    invitation = await store.invite(owner, team, Invite(projects=[project]))
    await store.accept(bob, invitation["invite"])
    return owner, bob, team, project, secret_project


async def test_team_project_selection_author_attribution_and_sharing_revocation(store):
    owner, bob, team, project, secret = await team_fixture(store)
    await store.push(owner, [operation("Trading shared decision"), operation("Private hidden decision", project="private")])
    await store.sharing(owner, team, [ShareMapping(source_project="app", project_id=project),
                                      ShareMapping(source_project="private", project_id=secret)])
    result = await store.search(bob, "decision", team=team)
    assert [m["text"] for m in result["memories"]] == ["Trading shared decision"]
    assert result["memories"][0]["author"] == "Alice"
    assert (await store.search(bob, "decision"))["memories"] == []
    assert len((await store.brief(bob, team, project))["items"]) == 1
    assert (await store.brief(bob, team, secret))["items"] == []
    with pytest.raises(Failure, match="project_not_allowed"):
        await store.sharing(bob, team, [ShareMapping(source_project="app", project_id=secret)])
    await store.sharing(owner, team, [])
    assert (await store.search(bob, "decision", team=team))["memories"] == []


async def test_team_invites_expiry_single_use_viewer_and_leave(store):
    owner, bob, team, project, _ = await team_fixture(store)
    _, eve = await account(store, "Eve")
    invite = await store.invite(owner, team, Invite(role="viewer", projects=[project]))
    await store.accept(eve, invite["invite"])
    with pytest.raises(Failure, match="invite_expired_or_used"):
        await store.accept(bob, invite["invite"])
    with pytest.raises(Failure, match="viewer_cannot_share"):
        await store.sharing(eve, team, [])
    await store.remove_member(owner, team, bob.user_id)
    with pytest.raises(Failure, match="team_not_found"):
        await store.brief(bob, team, project)
    expired = await store.invite(owner, team, Invite(projects=[project]))
    await store.pool.execute("UPDATE am_collab.invites SET expires_at=now()-interval '1 second'")
    with pytest.raises(Failure, match="invite_expired_or_used"):
        await store.accept(bob, expired["invite"])


@asynccontextmanager
async def running(embedder=None):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.close()
    url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(create_app(Store(DSN, embedder, memory_engine=ProtocolEngine()), url),
        host="127.0.0.1", port=port, log_level="critical", access_log=False))
    task = asyncio.create_task(server.serve())
    try:
        async with asyncio.timeout(15):
            while not server.started:
                if task.done():
                    await task
                await asyncio.sleep(.01)
        yield url
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 15)


async def test_actual_http_offline_outbox_two_pcs_reconnect_and_identity_guard(store, tmp_path):
    connection, actor = await account(store)
    key2 = await store.create_device(actor, "Laptop", True)
    async with running() as url:
        a = Replica(tmp_path / "desktop.sqlite", Remote(url, connection["token"]))
        b = Replica(tmp_path / "laptop.sqlite", Remote(url, key2["token"]))
        try:
            await asyncio.to_thread(a.connect)
            a.stage("app", "Remember PR assignee Jenny")
            result = await asyncio.to_thread(a.cycle)
            assert (result["pushed"], result["pulled"], result["cursor"], result["state"]) == (1, 1, 1, "synced")
            await asyncio.to_thread(b.cycle)
            assert b.list_memories()[0]["text"] == "Remember PR assignee Jenny"
            mid = b.list_memories()[0]["id"]
            b.stage("app", "Remember PR assignee Kim", memory_id=mid)
            await asyncio.to_thread(b.cycle)
            await asyncio.to_thread(a.cycle)
            assert a.list_memories()[0]["text"].endswith("Kim")
            _, outsider = await account(store, "Other account")
            other_key = await store.create_device(outsider, "Other", True)
            a.remote = Remote(url, other_key["token"])
            with pytest.raises(Failure, match="destination_changed"):
                await asyncio.to_thread(a.cycle)
        finally:
            a.close()
            b.close()


async def test_real_http_mcp_auth_tools_recall_and_session_context(store):
    connection, actor = await account(store)
    await store.push(actor, [operation()])
    async with running() as url:
        async with httpx2.AsyncClient(trust_env=False) as http:
            assert (await http.get(url + "/v1/me")).status_code == 401
            assert (await http.post(url + "/v1/sync/ops", content=b"x" * 1_048_577,
                headers={"Authorization": "Bearer " + connection["token"]})).status_code == 413
            assert (await http.get(url + "/v1/me", headers={"Authorization": "Bearer " + connection["token"], "Origin": "https://evil.example"})).status_code == 403
        async with (
            httpx2.AsyncClient(trust_env=False, headers={"Authorization": "Bearer " + connection["token"]}) as http,
            streamable_http_client(url + "/mcp", http_client=http) as (read, write),
            ClientSession(read, write) as session,
        ):
                initialized = await session.initialize()
                assert "session_start_context" in initialized.instructions
                assert {tool.name for tool in (await session.list_tools()).tools} == {"setup_status", "recall", "sync_retain", "team_brief", "team_search", "session_start_context"}
                result = await session.call_tool("session_start_context", {"project": "app", "query": "reviewers"})
                assert not result.is_error
                assert json.loads(result.content[0].text)["personal"]["memories"][0]["text"].endswith("PRs")


async def test_lost_acknowledgement_replays_without_duplicates(store, tmp_path):
    connection, _ = await account(store)
    async with running() as url:
        class LostAck(Remote):
            failed = False

            def request(self, path, value=None, **kwargs):
                result = super().request(path, value, **kwargs)
                if path.endswith("/ops") and not self.failed:
                    self.failed = True
                    raise OSError("synthetic lost acknowledgement")
                return result

        replica = Replica(tmp_path / "offline.sqlite", LostAck(url, connection["token"]))
        try:
            await asyncio.to_thread(replica.connect)
            replica.stage("app", "offline memory")
            with pytest.raises(OSError):
                await asyncio.to_thread(replica.cycle)
            assert replica.db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 1
            await asyncio.to_thread(replica.cycle)
            assert len(replica.list_memories()) == 1
            assert replica.db.execute("SELECT cursor FROM state").fetchone()[0] == 1
        finally:
            replica.close()


async def test_real_e5_pgvector_semantic_search(store, shared_e5):
    directory = os.environ.get("AM_COLLAB_TEST_E5")
    manifest = os.environ.get("AM_COLLAB_TEST_E5_MANIFEST")
    if not directory or not manifest:
        pytest.skip("Set E5 assets for real ONNX test")
    if not os.environ.get("AM_UNIFIED_TEST_RECEIPT"):
        pytest.skip("Semantic retrieval requires the isolated real Hindsight runtime")
    from test_unified_contract import engine
    store.memory_engine = engine()
    store.embedder = shared_e5
    _, actor = await account(store)
    op = operation("Pull requests require four reviewers and Jenny as assignee.")
    await store.push(actor, [op])
    found = await store.search(actor, "PR 리뷰 담당자 규칙", project="app")
    assert found["semantic"]
    assert [(str(memory["id"]), memory["text"]) for memory in found["memories"]] == [
        (str(op.memory_id), op.text)
    ]
