from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx2
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from test_collaboration import account, running

from agents_memory_collab.client import Remote, Replica
from agents_memory_collab.hindsight import HindsightBridge
from agents_memory_collab.web import Boundary


async def test_native_stdio_proxy_connects_to_real_authenticated_mcp(store):
    binary = os.environ.get("AM_COLLAB_TEST_PROXY")
    if not binary:
        pytest.skip("Set the compiled proxy path")
    connection, _ = await account(store)
    async with running() as url:
        parameters = StdioServerParameters(command=binary, args=["--url", url],
            env=dict(os.environ, AM_COLLAB_TOKEN=connection["token"]))
        async with stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            status = await session.call_tool("setup_status", {})
            assert json.loads(status.content[0].text)["ready"]


async def test_hindsight_bridge_only_reads_memory_units_and_deduplicates(store, tmp_path):
    connection, _ = await account(store)
    async with running() as url:
        replica = Replica(tmp_path / "bridge.sqlite", Remote(url, connection["token"]))
        await asyncio.to_thread(replica.connect)
        bridge = HindsightBridge(replica, "http://127.0.0.1:19999", "selected-bank", "app")
        source = {"items": [{"id": "stored-memory-id", "text": "Approved memory only", "original_text": "DO NOT EXPORT PROMPT"}], "total": 1}
        bridge.page = lambda offset: source
        try:
            assert bridge.stage()["staged"] == 1
            assert bridge.stage()["staged"] == 0
            pending = replica.db.execute("SELECT body FROM outbox").fetchone()[0]
            assert "DO NOT EXPORT" not in pending and "Approved memory" in pending
            await asyncio.to_thread(replica.cycle)
            source["items"][0]["text"] = "Updated approved memory"
            assert bridge.stage()["staged"] == 1
            await asyncio.to_thread(replica.cycle)
            assert replica.list_memories()[0]["revision"] == 2
            bridge.page = lambda offset: (_ for _ in ()).throw(OSError("source offline"))
            with pytest.raises(OSError):
                bridge.stage()
            assert len(replica.list_memories()) == 1
        finally:
            replica.close()


async def test_rest_team_membership_and_search_contract(store):
    owner_key, _ = await account(store)
    member_key, _ = await account(store, "Member")
    async with running() as url, httpx2.AsyncClient(trust_env=False) as http:
        owner = {"Authorization": "Bearer " + owner_key["token"]}
        member = {"Authorization": "Bearer " + member_key["token"]}
        team = (await http.post(url + "/v1/teams", headers=owner, json={"name": "Team"})).json()["id"]
        base = url + "/v1/teams/" + team
        project = (await http.post(base + "/projects", headers=owner, json={"name": "App"})).json()["id"]
        invitation = (await http.post(base + "/invites", headers=owner, json={"projects": [project]})).json()["invite"]
        assert (await http.post(url + "/v1/invites/accept", headers=member, json={"invite": invitation})).status_code == 200
        assert (await http.put(base + "/sharing", headers=member, json={"mappings": [{"source_project": "app", "project_id": project}]})).json() == {"shared_projects": 1}
        assert (await http.post(base + "/search", headers=member, json={"query": "memory"})).json()["memories"] == []
        assert (await http.post(base + "/leave", headers=member, json={})).status_code == 200
        assert (await http.post(base + "/search", headers=member, json={"query": "memory"})).status_code == 404


def test_replica_rejects_another_server_and_concurrent_worker(tmp_path):
    replica = Replica(tmp_path / "owned.sqlite", Remote("http://127.0.0.1:19998", "amc_" + "x" * 43))
    try:
        with replica.db:
            replica.db.execute("UPDATE worker SET owner='other',expires=9999999999")
        with pytest.raises(Exception, match="replica_worker_busy"):
            replica.cycle()
    finally:
        replica.close()


@pytest.mark.parametrize("keep", ["local", "server"])
async def test_two_device_offline_conflict_requires_explicit_resolution(store, tmp_path, keep):
    connection, _ = await account(store)
    async with running() as url:
        a = Replica(tmp_path / "first.sqlite", Remote(url, connection["token"]))
        b = Replica(tmp_path / "second.sqlite", Remote(url, connection["token"]))
        try:
            await asyncio.to_thread(a.connect)
            mid = a.stage("app", "Original memory")["memory_id"]
            await asyncio.to_thread(a.cycle)
            await asyncio.to_thread(b.cycle)
            a.stage("app", "First PC update", memory_id=mid)
            b.stage("app", "Second PC update", memory_id=mid)
            await asyncio.to_thread(a.cycle)
            result = await asyncio.to_thread(b.cycle)
            assert result["state"] == "needs_review"
            assert result["pending"][0]["error"] == "revision_conflict"
            assert b.db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 1
            await asyncio.to_thread(b.resolve, mid, keep)
            await asyncio.to_thread(b.cycle)
            await asyncio.to_thread(a.cycle)
            expected = "Second PC update" if keep == "local" else "First PC update"
            assert a.list_memories()[0]["text"] == expected
            assert b.list_memories()[0]["text"] == expected
        finally:
            a.close()
            b.close()


@pytest.mark.parametrize("kind", ["summary", "prompt"])
async def test_forget_preserves_kind_after_prompt_consent_is_revoked(store, tmp_path, kind):
    key, actor = await account(store)
    await store.preferences(actor, True)
    async with running() as url:
        replica = Replica(tmp_path / "delete.sqlite", Remote(url, key["token"]))
        try:
            await asyncio.to_thread(replica.connect)
            mid = replica.stage("app", "Selected text", kind=kind, allow_prompts=True)["memory_id"]
            await asyncio.to_thread(replica.cycle)
            await store.preferences(actor, False)
            replica.stage("app", memory_id=mid, deleted=True)
            await asyncio.to_thread(replica.cycle)
            assert replica.list_memories() == []
        finally:
            replica.close()


async def test_boundary_reserves_capacity_before_any_await():
    gate = asyncio.Event()
    admitted, rejected = 0, 0

    async def app(scope, receive, send):
        nonlocal admitted
        admitted += 1

    async def receive():
        await gate.wait()
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        nonlocal rejected
        if message["type"] == "http.response.start" and message["status"] == 503:
            rejected += 1

    boundary = Boundary(app, None, "http://127.0.0.1:18350")
    scope = {"type": "http", "path": "/healthz", "method": "GET", "headers": [(b"host", b"127.0.0.1:18350")]}
    tasks = [asyncio.create_task(boundary(dict(scope), receive, send)) for _ in range(100)]
    await asyncio.sleep(0)
    assert boundary.active == 64
    gate.set()
    await asyncio.gather(*tasks)
    assert admitted == 64 and rejected == 36 and boundary.active == 0
