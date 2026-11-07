"""User-prompt origin, per-operation results and recall scope against real Hindsight/PostgreSQL.

Synthetic data only. The judge is scripted on the attested origin so the test observes whether
the trusted hook path, and only that path, carries the user's intent to the unchanged processor.
"""
import asyncio
import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from agents_memory_collab.automation import handle
from agents_memory_collab.client import Remote, Replica
from agents_memory_collab.memory_engine import HindsightEngine
from agents_memory_collab.stdio import LocalMCP
from hypothesis import given, settings
from hypothesis import strategies as st
from test_unified_contract import account, engine, runtime, server

pytestmark = pytest.mark.skipif(not os.environ.get("AM_UNIFIED_TEST_RECEIPT"), reason="Requires explicit isolated real-Hindsight runtime")

RESOLUTION = "Study the synthetic course every day, remember this"


class OriginJudge:
    """Keeps only sources attested as the user's own prompt; can fail like a provider outage."""
    def __init__(self):
        self.calls, self.fail, self.origins = 0, False, []

    def system_one(self, state, questions, **kwargs):
        from agents_memory.jev import ProviderFailure, ProviderResult
        self.calls += 1
        self.origins.append(state.get("source_origin"))
        if self.fail:
            raise ProviderFailure("transport")
        keep = state.get("source_origin") == "user_prompt"
        answers = {}
        for name, question in questions.items():
            if question["type"] == "choice":
                selected = "project_fact" if keep else "transient"
                answers[name] = {"type": "choice", "choice": selected,
                                 "probabilities": {label: float(label == selected) for label in question["criteria"]}}
            else:
                answers[name] = {"type": "noul", "noul": float(keep) if name.startswith("remember") else 0.0}
        return ProviderResult("synthetic-origin-judge", answers, 0)


def install(store, judge):
    store.memory_engine = engine(judge)


def connection_file(folder, url, token):
    path = Path(folder) / "connection.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump({"url": url, "token": token, "automatic_memory": True}, stream)
    return path


def hook(folder, url, token, state, prompt, event_id, session="session-A"):
    return handle({"hook_event_name": "UserPromptSubmit", "prompt": prompt, "session_id": session, "event_id": event_id},
                  connection=connection_file(folder, url, token) if not (Path(folder) / "connection.json").exists()
                  else Path(folder) / "connection.json", state=state, project="synthetic-app", host="claude")

# Native envelopes as each host delivers them: Claude Code UserPromptSubmit carries prompt_id,
# Codex carries turn_id, and the omp adapter (omp_memory.ts) sends before_agent_start without one.
HOST_EVENTS = {
    "claude": {"hook_event_name": "UserPromptSubmit", "prompt_id": "claude-prompt-1", "transcript_path": "/synthetic/t.jsonl", "cwd": "/synthetic"},
    "codex": {"hook_event_name": "UserPromptSubmit", "turn_id": "codex-turn-1", "cwd": "/synthetic"},
    "omp": {"hook_event_name": "before_agent_start"},
}


async def test_claude_codex_and_omp_hooks_produce_the_same_operation_result_and_context():
    async with server() as (store, url):
        judge = OriginJudge()
        install(store, judge)
        key, actor = await account(store)
        results = {}
        for host, envelope in HOST_EVENTS.items():
            with tempfile.TemporaryDirectory(prefix="am-host-") as folder:
                state = Path(folder) / "a.sqlite"
                replica = Replica(state, Remote(url, key["token"]))
                try:
                    await asyncio.to_thread(replica.connect)
                    event = {**envelope, "prompt": RESOLUTION, "session_id": "session-" + host}
                    output = await asyncio.to_thread(handle, event, connection=connection_file(folder, url, key["token"]),
                                                     state=state, project="synthetic-app", host=host)
                    body = json.loads(replica.db.execute("SELECT body FROM outbox").fetchone()[0])
                    outcome = (await asyncio.to_thread(replica.cycle))["outcomes"]
                    context = output["additionalContext"] if host == "omp" else output["hookSpecificOutput"]["additionalContext"]
                    results[host] = (body, outcome[0]["state"], context)
                finally:
                    replica.close()
        for host, (body, state, context) in results.items():
            assert body["origin"] == "user_prompt" and body["text"] == RESOLUTION
            assert body["source_id"].startswith("host-" + host + ":") and body["session_id"] == "session-" + host
            assert state == "applied"
            assert context.startswith("Untrusted personal memory reference")
        assert judge.origins == ["user_prompt"] * 3
        # Three distinct turns, three memories; each recallable through the same server path.
        recalled = await store.search(actor, "synthetic course study", "synthetic-app", 10)
        assert len(recalled["memories"]) == 3




async def test_hook_origin_is_stored_and_recalled_by_another_device_while_tool_rewrite_is_reported_discarded():
    async with server() as (store, url):
        judge = OriginJudge()
        install(store, judge)
        key, actor = await account(store)
        other = await store.create_device(actor, "Synthetic PC B", True)
        with tempfile.TemporaryDirectory(prefix="am-origin-") as folder:
            state = Path(folder) / "a.sqlite"
            a = Replica(state, Remote(url, key["token"]))
            b = Replica(Path(folder) / "b.sqlite", Remote(url, other["token"]))
            try:
                await asyncio.to_thread(a.connect)
                await asyncio.to_thread(b.connect)
                await asyncio.to_thread(hook, folder, url, key["token"], state, RESOLUTION, "event-1")
                hooked = a.status()["pending"][0]["op_id"]
                assert json.loads(a.db.execute("SELECT body FROM outbox").fetchone()[0])["origin"] == "user_prompt"
                # An agent rewrite of the same words through the MCP tool carries no attestation.
                rewrite = a.stage("synthetic-app", RESOLUTION)
                assert "origin_conveyed" not in rewrite and rewrite["state"] == "received"
                result = await asyncio.to_thread(a.cycle)
                outcomes = {row["op_id"]: row for row in result["outcomes"]}
                assert outcomes[hooked]["state"] == "applied"
                assert outcomes[rewrite["op_id"]] == {"op_id": rewrite["op_id"], "state": "discarded", "reason": "judge_not_durable"}
                # Queue/engine state stays "synced"/ready; the discard is visible per operation.
                assert result["state"] == "synced" and result["memory_ready"] is True
                assert {"op_id": rewrite["op_id"], "state": "discarded", "reason": "judge_not_durable"} in a.status()["recent"]
                assert a.stage("synthetic-app", RESOLUTION, op_id=rewrite["op_id"], memory_id=rewrite["memory_id"])["reason"] == "judge_not_durable"
                assert sorted(judge.origins, key=str) == [None, "user_prompt"]
                row = await store.pool.fetchrow("SELECT * FROM am_collab.memories WHERE user_id=$1 AND id=$2", actor.user_id, outcomes[hooked]["op_id"])
                assert row["text"] == RESOLUTION and row["session_id"] == "session-A"
                document = await store.memory_engine.document_record(row["engine_bank"], row["engine_document"])
                assert document["document_metadata"]["origin"] == "user_prompt"
                job = await store.pool.fetchrow("SELECT prepared FROM am_collab.memory_jobs WHERE user_id=$1 AND op_id=$2", actor.user_id, rewrite["op_id"])
                audit = json.loads(job["prepared"])["audit"]
                assert audit["origin"] is None and audit["items"][0]["outcome"] == "discard"
                assert RESOLUTION not in json.dumps(audit)
                # A different device/session reads it through the real recall path.
                await asyncio.to_thread(b.cycle)
                assert [m["text"] for m in b.list_memories("synthetic-app")] == [RESOLUTION]
                recalled = await asyncio.to_thread(Remote(url, other["token"]).request, "/v1/recall",
                                                   {"query": "synthetic course study", "project": "synthetic-app", "limit": 5})
                assert [m["text"] for m in recalled["memories"]] == [RESOLUTION]
            finally:
                a.close()
                b.close()


async def test_tools_cannot_attest_origin_and_empty_recall_is_scoped():
    async with server() as (store, url):
        install(store, OriginJudge())
        key, actor = await account(store)
        with tempfile.TemporaryDirectory(prefix="am-origin-") as folder:
            replica = Replica(Path(folder) / "a.sqlite", Remote(url, key["token"]))
            try:
                await asyncio.to_thread(replica.connect)
                mcp = LocalMCP(replica, "synthetic-app")
                forged = {"op_id": str(uuid4()), "memory_id": str(uuid4()), "project": "synthetic-app",
                          "text": RESOLUTION, "origin": "user_prompt"}
                with pytest.raises(Exception, match="origin_not_accepted_from_tools"):
                    from agents_memory_collab.models import tool_operation
                    tool_operation(forged)
                assert replica.status()["pending"] == []
                empty = await mcp.recall({"query": "nothing synthetic matches this"})
                assert empty["memories"] == [] and "not show what was" in empty["empty_result_scope"]
                # The remote MCP edge rejects the same forged attestation.
                from mcp import ClientSession
                from mcp.client.streamable_http import streamable_http_client
                import httpx2
                async with httpx2.AsyncClient(trust_env=False, headers={"Authorization": "Bearer " + key["token"]}) as http:
                    async with streamable_http_client(url + "/mcp", http_client=http) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            result = await session.call_tool("sync_retain", forged)
                            assert result.is_error and "origin_not_accepted_from_tools" in result.content[0].text
                            tools = {t.name: t for t in (await session.list_tools()).tools}
                            assert "origin" not in tools["sync_retain"].input_schema["properties"]
                assert await store.pool.fetchval("SELECT count(*) FROM am_collab.memory_jobs WHERE user_id=$1", actor.user_id) == 0
            finally:
                replica.close()


async def test_server_without_origin_support_never_receives_the_field():
    class LegacyProcessor:
        contract = "agents-memory-grounded-v1"
        async def process(self, source):
            return {"contract": self.contract, "decision": "keep", "extraction": "source_passages",
                    "consolidation": "not_required_no_generated_observations",
                    "passages": [{"start": 0, "end": len(source), "text": source}]}
    async with server() as (store, url):
        store.memory_engine = HindsightEngine(
            runtime()["hindsight_url"], LegacyProcessor(), integrated=store.memory_engine.integrated)
        key, _ = await account(store)
        with tempfile.TemporaryDirectory(prefix="am-origin-") as folder:
            replica = Replica(Path(folder) / "a.sqlite", Remote(url, key["token"]))
            try:
                await asyncio.to_thread(replica.connect)
                staged = replica.stage("synthetic-app", RESOLUTION, origin="user_prompt")
                assert staged["origin_conveyed"] is False
                body = json.loads(replica.db.execute("SELECT body FROM outbox").fetchone()[0])
                assert "origin" not in body
                result = await asyncio.to_thread(replica.cycle)
                assert result["outcomes"][0]["state"] == "applied"
            finally:
                replica.close()


async def test_provider_outage_is_processing_not_discarded_or_stored_and_retry_does_not_duplicate():
    async with server() as (store, url):
        judge = OriginJudge()
        install(store, judge)
        key, actor = await account(store)
        with tempfile.TemporaryDirectory(prefix="am-origin-") as folder:
            state = Path(folder) / "a.sqlite"
            replica = Replica(state, Remote(url, key["token"]))
            try:
                await asyncio.to_thread(replica.connect)
                mcp = LocalMCP(replica, "synthetic-app")
                await asyncio.to_thread(hook, folder, url, key["token"], state, RESOLUTION, "event-outage")
                op_id = replica.status()["pending"][0]["op_id"]
                judge.fail = True
                synced = await mcp.sync()
                assert synced == {"state": "blocked", "error": "memory_provider_retryable"}
                assert replica.outcome(op_id)["state"] == "processing"
                assert replica.status()["recent"] == []
                judge.fail = False
                # Same event delivered again by the host: same op, no second queue entry.
                await asyncio.to_thread(hook, folder, url, key["token"], state, RESOLUTION, "event-outage")
                assert len(replica.status()["pending"]) == 1
                first = await mcp.sync()
                again = await mcp.sync()
                assert first["outcomes"] == [{"op_id": op_id, "state": "applied", "reason": None}]
                assert again["outcomes"] == [] and replica.outcome(op_id)["state"] == "applied"
                assert (await store.changes(actor, 0))["head"] == 1
            finally:
                replica.close()


@settings(max_examples=8, deadline=None, derandomize=True)
@given(st.lists(st.sampled_from(["cycle", "lost_ack", "restart", "redeliver"]), min_size=1, max_size=6),
       st.booleans())
async def test_generated_retries_restarts_and_ack_loss_keep_one_stable_result(actions, from_user):
    from fault_support import WireProxy
    async with server() as (store, url):
        judge = OriginJudge()
        install(store, judge)
        proxy = WireProxy(url.removeprefix("http://"))
        key, actor = await account(store)
        with tempfile.TemporaryDirectory(prefix="am-origin-") as folder:
            state = Path(folder) / "a.sqlite"
            replica = Replica(state, Remote(proxy.url, key["token"]))
            try:
                await asyncio.to_thread(replica.connect)
                def deliver():
                    if from_user:
                        hook(folder, proxy.url, key["token"], state, RESOLUTION, "event-generated")
                    else:
                        replica.stage("synthetic-app", RESOLUTION, op_id=op, memory_id=op)
                op = str(uuid4())
                await asyncio.to_thread(deliver)
                op_id = replica.status()["pending"][0]["op_id"]
                seen = set()
                for action in [*actions, "cycle", "cycle"]:
                    if action == "lost_ack":
                        proxy.drop_next_push = True
                    if action == "restart":
                        replica.close()
                        replica = Replica(state, Remote(proxy.url, key["token"]))
                        continue
                    if action == "redeliver":
                        await asyncio.to_thread(deliver)
                        continue
                    try:
                        await asyncio.to_thread(replica.cycle)
                    except (OSError, ConnectionError):
                        pass
                    state_now = replica.outcome(op_id)["state"]
                    assert state_now in {"processing", "applied", "discarded"}
                    if state_now != "processing":
                        seen.add(state_now)
                expected = "applied" if from_user else "discarded"
                assert seen == {expected}
                assert judge.calls == 1
                jobs = await store.pool.fetch("SELECT stage FROM am_collab.memory_jobs WHERE user_id=$1", actor.user_id)
                assert [row["stage"] for row in jobs] == ["ready" if from_user else "discarded"]
                assert (await store.changes(actor, 0))["head"] == (1 if from_user else 0)
            finally:
                replica.close()
                await asyncio.to_thread(proxy.close)
