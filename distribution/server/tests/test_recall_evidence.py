"""SQL publication of scripted native nominations; no model-quality claims."""

from uuid import uuid4

import pytest
from agents_memory_collab.models import Operation
from agents_memory_collab.protocol import canonical
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
async def test_different_native_fragments_of_identical_sources_share_one_result_slot(store):
    _, actor = await account(store)
    body = "The cache TTL is 37 seconds.\nThe namespace is cache-v7."
    first = await retained(store, actor, body)
    second = await retained(store, actor, body)
    other = await retained(store, actor, "Backups are retained for 29 days.")
    bank = first["engine_bank"]
    store.memory_engine = RecallEngine({bank: [
        hit("The cache TTL is 37 seconds.", first),
        hit("The namespace is cache-v7.", second),
        hit(other["text"], other),
    ]})

    result = await store.search(actor, "cache and backup policy", project="app", limit=2)

    assert [item["text"] for item in result["memories"]] == [body, other["text"]]
    assert {source["id"] for source in result["memories"][0]["sources"]} == {
        str(first["id"]), str(second["id"]),
    }
    assert str(result["memories"][0]["id"]) == min(str(first["id"]), str(second["id"]))
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


@pytest.mark.asyncio
async def test_matching_fragment_cannot_drop_the_sources_final_exception(store):
    _, actor = await account(store)
    text = (
        "Atlas backup retention is 29 days.\n"
        + "Audit details apply to regular backups.\n" * 100
        + "Records under legal hold must never be deleted, regardless of age."
    )
    source = await retained(store, actor, text)
    store.memory_engine = RecallEngine({source["engine_bank"]: [
        hit("Atlas backup retention is 29 days.", source),
    ]})

    result = await store.search(actor, "Atlas backup retention", project="app")

    assert len(result["memories"]) == 1
    assert result["memories"][0]["text"] == text
    assert result["memories"][0]["sources"] == [{
        "id": str(source["id"]), "revision": source["revision"], "project": "app",
    }]


@pytest.mark.asyncio
@pytest.mark.parametrize("composite", [False, True])
async def test_complete_source_budget_skips_whole_evidence_without_losing_qualifiers(
    store, monkeypatch, composite,
):
    import agents_memory_collab.store as store_module

    monkeypatch.setattr(store_module, "MAX_SEARCH_RESPONSE_BYTES", 1200)
    _, actor = await account(store)
    large = await retained(store, actor, "Shared release rule. " + "가" * 1000 + "\nNever delete legal holds.")
    small = await retained(store, actor, 'Preserve "legal holds".\nNever delete them.')
    bank = large["engine_bank"]
    hits = ([hit("Shared release rule.", large, small)] if composite else [
        hit("Shared release rule.", large), hit(small["text"], small),
    ])
    store.memory_engine = RecallEngine({bank: hits})

    result = await store.search(actor, "release retention", project="app", limit=1)

    assert [item["text"] for item in result["memories"]] == ([] if composite else [small["text"]])
    assert result["partial"] is True
    assert result["omitted_due_to_budget"] == 1
    assert len(canonical(result).encode("utf-8")) <= 1200


@pytest.mark.asyncio
async def test_budget_omission_is_not_reported_as_no_matching_memory():
    from agents_memory_collab.stdio import BUDGET_SCOPE, LocalMCP

    class Remote:
        def request(self, path, value):
            return {"memories": [], "partial": True, "omitted_due_to_budget": 1}

    class Replica:
        remote = Remote()

        def status(self):
            return {"memory_contract": "agents-memory-grounded-v1"}

    result = await LocalMCP(Replica(), "app").recall({"query": "release rules", "project": "app"})

    assert result["empty_result_scope"] == BUDGET_SCOPE
    assert result["partial"] is True and result["omitted_due_to_budget"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "What are the bounds and defaults of Widget.limit?",
    "Widget.limit의 기본값과 필수 여부는?",
    "Explain `widget.limit`.",
    "For model Widget, explain Widget.limit.",
])
async def test_qualified_identifier_keeps_matching_native_sources_before_limit(store, query):
    _, actor = await account(store)
    identifier = "widget.limit" if "`widget.limit`" in query else "Widget.limit"
    wrong = await retained(store, actor, "Different.limit has a default of 5.")
    shape = await retained(store, actor, f"{identifier} has integer shape.")
    bounds = await retained(store, actor, f"{identifier} has a default of 7 and a maximum of 11.")
    required = await retained(store, actor, f"{identifier} is optional. Preserve its exception.")
    bank = shape["engine_bank"]
    store.memory_engine = RecallEngine({bank: [
        hit(wrong["text"], wrong), hit(shape["text"], shape),
        hit(bounds["text"], bounds), hit(required["text"], required),
    ]})

    result = await store.search(actor, query, project="app", limit=3)

    assert [item["text"] for item in result["memories"]] == [shape["text"], bounds["text"], required["text"]]
    assert {s["id"] for item in result["memories"] for s in item["sources"]} == {
        str(row["id"]) for row in (shape, bounds, required)
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("different", ["Widget.limits", "OtherWidget.limit", "Other.Widget.limit", "Widget.limit.maximum"])
async def test_qualified_identifier_does_not_match_a_prefix_or_another_qualified_name(store, different):
    _, actor = await account(store)
    wrong = await retained(store, actor, f"{different} has a default of 5.")
    store.memory_engine = RecallEngine({wrong["engine_bank"]: [hit(wrong["text"], wrong)]})

    result = await store.search(actor, "Explain Widget.limit", project="app")

    assert result["memories"] == []


@pytest.mark.asyncio
async def test_identifier_filter_uses_full_authorized_source_not_only_native_fragment(store):
    _, actor = await account(store)
    text = "Widget.limit is optional.\nProduction clients must still send an audit token."
    source = await retained(store, actor, text)
    store.memory_engine = RecallEngine({source["engine_bank"]: [
        hit("Production clients must still send an audit token.", source),
    ]})

    result = await store.search(actor, "Explain Widget.limit", project="app")

    assert [item["text"] for item in result["memories"]] == [text]


@pytest.mark.asyncio
async def test_multiple_identifiers_preserve_evidence_for_either_requested_name(store):
    _, actor = await account(store)
    rows = [await retained(store, actor, text) for text in [
        "Widget.limit defaults to 7.", "Source.limit defaults to 5.", "Other.limit defaults to 99.",
    ]]
    store.memory_engine = RecallEngine({rows[0]["engine_bank"]: [hit(row["text"], row) for row in rows]})

    result = await store.search(actor, "Compare Widget.limit and Source.limit", project="app")

    assert [item["text"] for item in result["memories"]] == [row["text"] for row in rows[:2]]


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "Explain the model Widget and its required fields.",
    "What does class Widget require?",
    "Describe type Widget.",
    "model Widget의 필수 필드는?",
])
async def test_named_type_keeps_its_root_and_field_evidence_before_limit(store, query):
    _, actor = await account(store)
    rows = [await retained(store, actor, text) for text in [
        "OtherWidget is an object.", "WidgetExtra requires a token.",
        "Widget is an object with additionalProperties=false.",
        "Widget requires the limit field.", "Widget.limit has integer shape.",
    ]]
    store.memory_engine = RecallEngine({rows[0]["engine_bank"]: [hit(rows[i]["text"], rows[i]) for i in [0,1,4,2,3]]})

    result = await store.search(actor, query, project="app", limit=3)

    assert [item["text"] for item in result["memories"]] == [row["text"] for row in rows[2:]]


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "What is the backup policy?", "Use e.g. our backup policy.",
    "What is documented at https://GitHub.com/example?", "Check example.com backups.",
    "What model should we use for backups?",
])
async def test_ordinary_prose_abbreviations_and_urls_preserve_native_nominations(store, query):
    _, actor = await account(store)
    first = await retained(store, actor, "Backups are retained for 29 days.")
    second = await retained(store, actor, "Legal holds must not be deleted.")
    store.memory_engine = RecallEngine({first["engine_bank"]: [hit(first["text"], first), hit(second["text"], second)]})

    result = await store.search(actor, query, project="app")

    assert [item["text"] for item in result["memories"]] == [first["text"], second["text"]]
