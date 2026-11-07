"""SQL publication of scripted native nominations; no model-quality claims."""

from uuid import uuid4

import pytest
from agents_memory_collab.models import Operation
from engine_double import ProtocolEngine
from test_collaboration import account, operation


class RecallEngine(ProtocolEngine):
    integrated = True

    def __init__(self, hits):
        self.hits = hits

    async def recall(self, bank, query):
        return self.hits.get(bank, [])


async def retained(store, actor, text, **kwargs):
    op = operation(text, **kwargs)
    await store.push(actor, [op])
    row = await store.pool.fetchrow(
        "SELECT * FROM am_collab.memories WHERE user_id=$1 AND id=$2",
        actor.user_id, op.memory_id,
    )
    return row


def hit(text, *rows):
    return {"id": str(uuid4()), "text": text,
            "source_documents": [row["engine_document"] for row in rows]}


@pytest.mark.asyncio
async def test_duplicate_native_evidence_cannot_displace_a_distinct_top_result(store):
    _, actor = await account(store)
    repeated = "Release approval requires two reviewers.\nEmergency fixes still need an audit."
    first = await retained(store, actor, repeated)
    second = await retained(store, actor, repeated)
    other = await retained(store, actor, "Production backups are retained for 29 days.")
    bank = first["engine_bank"]
    store.memory_engine = RecallEngine({bank: [
        hit(repeated, first, second), hit(repeated, first), hit(repeated, second),
        hit(other["text"], other),
    ]})

    result = await store.search(actor, "release rules", project="app", limit=2)

    assert [item["text"] for item in result["memories"]] == [repeated, other["text"]]
    assert {source["id"] for source in result["memories"][0]["sources"]} == {
        str(first["id"]), str(second["id"]),
    }
    assert result["memories"][0]["score"] == 1


@pytest.mark.asyncio
async def test_distinct_multiline_evidence_keeps_its_order_and_every_source(store):
    _, actor = await account(store)
    first = await retained(store, actor, "Release rule.\nKeep its exception.")
    second = await retained(store, actor, "Independent audit rule.\nKeep its condition.")
    bank = first["engine_bank"]
    store.memory_engine = RecallEngine({bank: [
        hit(first["text"], first, second), hit(second["text"], first, second),
        hit(first["text"], first, second),
    ]})

    result = await store.search(actor, "release rules", project="app")

    assert len(result["memories"]) == 1
    assert result["memories"][0]["text"] == first["text"] + "\n" + second["text"]
    assert {source["id"] for source in result["memories"][0]["sources"]} == {
        str(first["id"]), str(second["id"]),
    }


@pytest.mark.asyncio
async def test_unavailable_source_does_not_supply_provenance_for_a_duplicate(store):
    _, actor = await account(store)
    first = await retained(store, actor, "Keep an audit for releases.")
    second = await retained(store, actor, first["text"])
    await store.push(actor, [Operation(
        op_id=uuid4(), project="app", memory_id=second["id"],
        base_revision=second["revision"], deleted=True,
    )])
    bank = first["engine_bank"]
    store.memory_engine = RecallEngine({bank: [
        hit(first["text"], first, second), hit(first["text"], first),
    ]})

    result = await store.search(actor, "audit", project="app")

    assert len(result["memories"]) == 1
    assert result["memories"][0]["text"] == first["text"]
    assert result["memories"][0]["sources"] == [{
        "id": str(first["id"]), "revision": first["revision"], "project": "app",
    }]
    assert result["memories"][0]["score"] == .5


@pytest.mark.asyncio
async def test_equal_text_in_different_project_banks_keeps_separate_provenance(store):
    _, actor = await account(store)
    first = await retained(store, actor, "Keep release audits.", project="app-a")
    second = await retained(store, actor, first["text"], project="app-b")
    store.memory_engine = RecallEngine({
        first["engine_bank"]: [hit(first["text"], first)],
        second["engine_bank"]: [hit(second["text"], second)],
    })

    result = await store.search(actor, "audit")

    assert len(result["memories"]) == 2
    assert {item["project"] for item in result["memories"]} == {"app-a", "app-b"}
    assert all(len(item["sources"]) == 1 for item in result["memories"])


@pytest.mark.asyncio
@pytest.mark.parametrize("second_text", [
    "Release audits are required",
    "Release audits are never required.",
    "Release audits are required.\nOnly production releases are in scope.",
])
async def test_similar_text_is_not_deduplicated_as_identical_evidence(store, second_text):
    _, actor = await account(store)
    first = await retained(store, actor, "Release audits are required.")
    second = await retained(store, actor, second_text)
    bank = first["engine_bank"]
    store.memory_engine = RecallEngine({bank: [
        hit(first["text"], first), hit(second["text"], second),
    ]})

    result = await store.search(actor, "release audits", project="app")

    assert [item["text"] for item in result["memories"]] == [first["text"], second_text]
    assert [item["sources"] for item in result["memories"]] == [
        [{"id": str(row["id"]), "revision": row["revision"], "project": "app"}]
        for row in (first, second)
    ]
