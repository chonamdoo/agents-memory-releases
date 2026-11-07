import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("search_evaluation", ROOT / "run.py")
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def rows(hits=40, joint=40):
    return [
        {"kind": "answerable", "any_hit": index < hits, "all_evidence": index < joint,
         "noise": 0, "retrieved": ["a", "b"] if index < hits else []}
        for index in range(40)
    ] + [{"kind": "unrelated", "any_hit": False, "all_evidence": False,
          "noise": 0, "retrieved": []} for _ in range(12)]


def test_fixture_freeze_and_topic_split_do_not_share_inputs():
    fixture = json.loads((ROOT / "fixture.json").read_text())
    registration = json.loads((ROOT / "registration.json").read_text())
    assert evaluation.digest(ROOT / "fixture.json") == registration["fixture_sha256"]
    topics, texts, queries = [], [], []
    for name, split in fixture["splits"].items():
        documents = {row["id"]: row for row in split["documents"]}
        assert len(documents) == len(split["documents"]) == 60
        assert len({row["id"] for row in split["queries"]}) == 52
        assert sum(row["kind"] == "answerable" for row in split["queries"]) == 40
        for row in split["queries"]:
            assert set(row["required_sources"]) <= set(row["relevant_sources"]) <= set(documents)
            if row["kind"] == "answerable":
                assert len(row["required_sources"]) == 2
                assert all(documents[key]["topic"] == row["cluster"] for key in row["required_sources"])
            else:
                assert row["required_sources"] == row["relevant_sources"] == []
        topics.append({row["topic"] for row in documents.values()})
        texts.append({row["text"] for row in documents.values()})
        queries.append({row["query"] for row in split["queries"]})
        assert all(row["id"].startswith(name + "-") for row in split["queries"])
    assert all(not left & right for left, right in (topics, texts, queries))


@pytest.mark.parametrize(("hits", "expected"), [(35, False), (36, True), (40, True)])
def test_wilson_hit_floor_keeps_empty_failures_in_the_denominator(hits, expected):
    report = evaluation.metrics(rows(hits, hits))
    assert report["answerable_questions"] == 40
    assert report["any_hit_at_5"] == hits
    assert report["engineering_gate_pass"] is expected


def test_missing_joint_evidence_is_reported_separately_from_any_hit():
    report = evaluation.metrics(rows(joint=2))
    assert report["any_hit_at_5"] == 40
    assert report["all_required_evidence_at_5"] == 2


def test_no_results_are_not_a_passing_noise_measurement():
    report = evaluation.metrics(rows(0, 0))
    assert report["returned_sources"] == 0
    assert report["noise_wilson_95"] is None
    assert report["engineering_gate_pass"] is False


def test_a_false_positive_control_blocks_a_low_overall_noise_candidate():
    observed = rows()
    observed[-1].update(retrieved=["unrelated-source"], noise=1)
    report = evaluation.metrics(observed)
    assert report["noise_wilson_95"][1] < .30
    assert report["unrelated_abstained"] == 11
    assert report["engineering_gate_pass"] is False


async def test_fixture_admission_never_accepts_unregistered_source():
    processor = evaluation.ApprovedFixture([{"text": "The cache TTL is 37 seconds."}])
    with pytest.raises(ValueError, match="preregistered"):
        await processor.process("An unregistered source must not enter this corpus.")
