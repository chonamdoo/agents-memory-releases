"""Original-source discovery must preserve tenant, revision and processing fences."""
import hashlib
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx2
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import ValidationError

from agents_memory_collab.models import Failure, SourceSearch
from agents_memory_collab.stdio import LocalMCP
from engine_double import ProtocolEngine
from test_collaboration import account, operation, running


class SelectFirstLine(ProtocolEngine):
    async def prepare(self, source):
        text = source.splitlines()[0]
        return {"decision": "keep", "passages": [{"start": 0, "end": len(text), "text": text}]}


class Discard(ProtocolEngine):
    async def prepare(self, source):
        return {"decision": "discard", "passages": []}


async def captured(store, actor, body="The cache TTL is 37 seconds.\nThe namespace is cache-v7.", **kw):
    store.memory_engine = SelectFirstLine()
    op = operation(body, source_id="cache-fixture", session_id="session-A", **kw)
    await store.push(actor, [op])
    return op


async def test_original_fact_excluded_from_memory_is_independently_searchable(store):
    _, actor = await account(store)
    op = await captured(store, actor)
    published = await store.pool.fetchval("SELECT text FROM am_collab.memories WHERE user_id=$1 AND id=$2", actor.user_id, op.memory_id)
    assert "cache-v7" not in published
    assert (await store.search(actor, "namespace", "app"))["memories"] == []
    store.memory_engine = None
    found = await store.source_search(actor, "What is the cache namespace?", "app")
    assert found["search_kind"] == "lexical_original_sources" and not found["semantic"]
    assert len(found["sources"]) == 1
    source = found["sources"][0]
    assert source["id"] == str(op.op_id) and source["memory_id"] == str(op.memory_id)
    assert source["body"] == op.text
    assert source["body_sha256"] == hashlib.sha256(op.text.encode()).hexdigest()
    assert source["body_bytes"] == len(op.text.encode())
    assert source["memory_revision"] == 1 and source["operation_base_revision"] == 0
    assert source["source_id"] == "cache-fixture" and source["session_id"] == "session-A"
    assert source["evidence_role"] == "untrusted_original_source_not_verified_fact"


async def test_discarded_original_can_be_read_without_promoting_it_to_memory(store):
    _, actor = await account(store)
    store.memory_engine = Discard()
    op = operation("The transient namespace is sandbox-v9.")
    assert (await store.push(actor, [op]))["discarded"]
    found = await store.source_search(actor, "namespace", "app")
    assert found["sources"][0]["body"] == op.text
    assert found["sources"][0]["retention_decision"] == "discard"
    assert found["sources"][0]["memory_revision"] is None
    assert await store.pool.fetchval("SELECT count(*) FROM am_collab.memories WHERE user_id=$1", actor.user_id) == 0


async def test_modified_original_fails_integrity_before_disclosure(store):
    _, actor = await account(store)
    op = await captured(store, actor)
    await store.pool.execute("""UPDATE am_collab.memory_jobs
        SET original=jsonb_set(original,'{text}',to_jsonb('namespace tampered'::text))
        WHERE user_id=$1 AND op_id=$2""", actor.user_id, op.op_id)
    with pytest.raises(Failure, match="original_source_integrity_failed"):
        await store.source_search(actor, "namespace", "app")


@pytest.mark.parametrize(("column", "value"), [("project", "moved"), ("kind", "prompt")])
async def test_current_memory_scope_must_still_match_original(store, column, value):
    _, actor = await account(store)
    op = await captured(store, actor)
    assert column in {"project", "kind"}
    await store.pool.execute(f"UPDATE am_collab.memories SET {column}=$3 WHERE user_id=$1 AND id=$2",
                             actor.user_id, op.memory_id, value)
    assert (await store.source_search(actor, "namespace", "app"))["sources"] == []


async def test_owner_and_project_scope_precede_ranking_and_limits(store):
    _, alice = await account(store, "Alice")
    _, bob = await account(store, "Bob")
    for _ in range(12):
        await captured(store, bob, "Namespace namespace namespace foreign-private.")
        await captured(store, alice, "Namespace namespace namespace another-project.", project="other")
    own = await captured(store, alice, "Namespace selected-project.")
    found = await store.source_search(alice, "namespace", "app", 1)
    assert [s["id"] for s in found["sources"]] == [str(own.op_id)]
    assert "foreign-private" not in json.dumps(found, default=str)


async def test_edits_and_deletions_hide_old_originals_even_while_jobs_remain(store):
    _, actor = await account(store)
    first = await captured(store, actor, "The originalnamespace is obsolete.")
    replacement = first.model_copy(update={"op_id": uuid4(), "base_revision": 1, "text": "The currentnamespace is active."})
    await store.push(actor, [replacement])
    assert (await store.source_search(actor, "originalnamespace", "app"))["sources"] == []
    assert (await store.source_search(actor, "currentnamespace", "app"))["sources"][0]["memory_revision"] == 2
    await store.push(actor, [replacement.model_copy(update={"op_id": uuid4(), "base_revision": 2, "deleted": True, "text": None})])
    assert (await store.source_search(actor, "currentnamespace", "app"))["sources"] == []
    assert await store.pool.fetchval("SELECT count(*) FROM am_collab.memory_jobs WHERE user_id=$1 AND original->>'text' IS NOT NULL", actor.user_id) == 2


async def test_discarded_edit_does_not_outlive_the_memory_revision_it_targeted(store):
    _, actor = await account(store)
    original = await captured(store, actor, "The original namespace is cache-v1.")
    store.memory_engine = Discard()
    rejected = original.model_copy(update={"op_id": uuid4(), "base_revision": 1, "text": "The discardednamespace is only a suggestion."})
    await store.push(actor, [rejected])
    assert (await store.source_search(actor, "discardednamespace", "app"))["sources"]
    store.memory_engine = ProtocolEngine()
    await store.push(actor, [original.model_copy(update={"op_id": uuid4(), "base_revision": 1, "text": "The current namespace is cache-v2."})])
    assert (await store.source_search(actor, "discardednamespace", "app"))["sources"] == []


@pytest.mark.parametrize(("stage", "decision"), [
    ("received", "keep"), ("extracted", "keep"), ("indexed", "keep"),
    ("deleted", "keep"), ("ready", "review"), ("ready", "discard"), ("discarded", "keep"),
])
async def test_incomplete_or_inconsistent_processing_never_discloses_original(store, stage, decision):
    _, actor = await account(store)
    op = await captured(store, actor)
    await store.pool.execute("UPDATE am_collab.memory_jobs SET stage=$3,prepared=$4::jsonb WHERE user_id=$1 AND op_id=$2",
                             actor.user_id, op.op_id, stage, json.dumps({"decision": decision}))
    assert (await store.source_search(actor, "namespace", "app"))["sources"] == []


async def test_prompt_uploads_stay_out_of_original_search_even_after_consent(store):
    _, actor = await account(store)
    await store.preferences(actor, True)
    await captured(store, actor, "Private promptnamespace content.", kind="prompt")
    assert (await store.source_search(actor, "promptnamespace", "app"))["sources"] == []


async def test_revoked_device_cannot_query_originals(store):
    _, actor = await account(store)
    await captured(store, actor)
    device = await store.create_device(actor, "Personal reader", False)
    reader = await store.authenticate(device["token"])
    assert (await store.source_search(reader, "namespace", "app"))["sources"]
    await store.revoke_device(actor, UUID(device["credential_id"]))
    with pytest.raises(Failure, match="unauthorized"):
        await store.source_search(reader, "namespace", "app")


@pytest.mark.parametrize("args", [
    {"query": "namespace"}, {"query": " ", "project": "app"},
    {"query": "namespace", "project": "app", "limit": 11},
    {"query": "namespace", "project": "app", "limit": True},
    {"query": "namespace", "project": "app", "team_id": "foreign"},
    {"query": "bad\x00query", "project": "app"},
])
def test_explicit_bounded_personal_source_query(args):
    with pytest.raises(ValidationError):
        SourceSearch.model_validate(args)


async def test_http_and_mcp_discover_the_original_not_the_processed_projection(store):
    connection, actor = await account(store)
    op = await captured(store, actor)
    async with running() as url:
        async with httpx2.AsyncClient(trust_env=False) as public:
            assert (await public.post(url + "/v1/sources/search", json={"project": "app", "query": "namespace"})).status_code == 401
        async with httpx2.AsyncClient(trust_env=False, headers={"Authorization": "Bearer " + connection["token"]}) as http:
            response = await http.post(url + "/v1/sources/search", json={"project": "app", "query": "namespace"})
            assert response.status_code == 200 and response.json()["sources"][0]["body"] == op.text
            assert (await http.post(url + "/v1/sources/search", json={"query": "namespace"})).status_code == 400
            async with streamable_http_client(url + "/mcp", http_client=http) as (read, write), ClientSession(read, write) as session:
                await session.initialize()
                schema = next(t.input_schema for t in (await session.list_tools()).tools if t.name == "source_search")
                assert "project" in schema["required"]
                result = await session.call_tool("source_search", {"project": "app", "query": "namespace"})
                assert not result.is_error
                assert json.loads(result.content[0].text)["sources"][0]["body"] == op.text


async def test_stdio_source_search_is_online_and_never_falls_back_to_processed_cache():
    def request(path, args):
        assert path == "/v1/sources/search" and args["project"] == "explicit-project"
        return {"sources": [{"body": "Original namespace."}]}
    replica = SimpleNamespace(remote=SimpleNamespace(request=request))
    client = LocalMCP(replica, "startup-project")
    assert (await client.source_search({"project": "explicit-project", "query": "namespace"}))["sources"]
    def offline(*args):
        raise OSError("offline")
    replica.remote.request = offline
    with pytest.raises(Failure, match="original_source_search_requires_connection"):
        await client.source_search({"project": "explicit-project", "query": "namespace"})
