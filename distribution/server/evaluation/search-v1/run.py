"""Keyless search-only calibration and one-shot validation on preapproved synthetic sources."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from agents_memory_collab.memory_engine import HindsightEngine
from agents_memory_collab.models import Operation
from agents_memory_collab.store import Store

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT.parents[1] / "src/agents_memory_collab"
FLOORS = (.1, .05, .03, .02, .01, .003, .001, .0003, .0001, .00003)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def wilson(successes, count):
    if not count:
        return None
    z = 1.959963984540054
    p = successes / count
    scale = 1 + z * z / count
    center = (p + z * z / (2 * count)) / scale
    radius = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / scale
    return [max(0, center - radius), min(1, center + radius)]


class ApprovedFixture:
    contract = "agents-memory-grounded-v1"

    def __init__(self, documents):
        self.allowed = {item["text"] for item in documents}

    async def process(self, source):
        if source not in self.allowed:
            raise ValueError("Only preregistered synthetic source text is admitted")
        return {"contract": self.contract, "decision": "keep",
                "passages": [{"start": 0, "end": len(source), "text": source}],
                "extraction": "source_passages",
                "consolidation": "not_required_no_generated_observations"}


class DevelopmentEngine(HindsightEngine):
    """Cache one unfiltered native response per query; compare floors without new inference."""
    floor = .03

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.captured = {}

    async def request(self, path, value=None, method=None):
        if not path.endswith("/memories/recall"):
            return await super().request(path, value, method)
        key = path, value["query"]
        if key not in self.captured:
            self.captured[key] = await super().request(path, {**value, "min_scores": {}}, method)
        raw = self.captured[key]
        if raw is None:
            return None
        return {**raw, "results": [hit for hit in raw["results"]
                                   if hit["scores"]["reranker"] >= self.floor]}


class ValidationEngine(HindsightEngine):
    def __init__(self, *args, floor, **kwargs):
        super().__init__(*args, **kwargs)
        self.floor = floor
        self.captured = {}

    async def request(self, path, value=None, method=None):
        if path.endswith("/memories/recall") and value.get("min_scores") != {"reranker": self.floor}:
            raise ValueError("The production recall floor differs from the frozen candidate")
        result = await super().request(path, value, method)
        if path.endswith("/memories/recall"):
            self.captured[path, value["query"]] = result
        return result


def metrics(rows):
    positive = [row for row in rows if row["kind"] == "answerable"]
    controls = [row for row in rows if row["kind"] == "unrelated"]
    any_hit = sum(row["any_hit"] for row in positive)
    joint = sum(row["all_evidence"] for row in positive)
    noise = sum(row["noise"] for row in rows)
    returned = sum(len(row["retrieved"]) for row in rows)
    hit_interval, noise_interval = wilson(any_hit, len(positive)), wilson(noise, returned)
    abstained = sum(not row["retrieved"] for row in controls)
    eligible = (hit_interval is not None and hit_interval[0] >= .75
                and noise_interval is not None and noise_interval[1] <= .30
                and abstained == len(controls))
    return {"answerable_questions": len(positive), "any_hit_at_5": any_hit,
            "any_hit_wilson_95": hit_interval, "all_required_evidence_at_5": joint,
            "noise_sources": noise, "returned_sources": returned,
            "noise_wilson_95": noise_interval,
            "unrelated_abstained": abstained, "unrelated_questions": len(controls),
            "engineering_gate_pass": eligible}


async def main(args):
    if args.output.exists():
        raise ValueError("Select a new output directory; existing evidence is preserved")
    fixture_path = ROOT / "fixture.json"
    fixture = json.loads(fixture_path.read_text())
    manifest = json.loads((ROOT / "registration.json").read_text())
    if digest(fixture_path) != manifest["fixture_sha256"] or list(FLOORS) != manifest["development_floors"]:
        raise ValueError("The preregistered fixture or candidate grid changed")
    receipt = json.loads(args.receipt.read_text())
    if receipt.get("synthetic_only") is not True or receipt.get("processing") != "integrated":
        raise ValueError("An explicit synthetic integrated runtime is required")
    if urlsplit(receipt["dsn"]).hostname != "127.0.0.1":
        raise ValueError("The synthetic database must be on loopback")
    sources = {name: digest(PACKAGE / name) for name in ("memory_engine.py", "store.py", "stdio.py")}
    registration = {"fixture_sha256": digest(fixture_path), "split": args.split,
                    "product_source_sha256": sources, "external_jev_api_calls": 0,
                    "annotation": fixture["annotation"], "scope": "synthetic_engineering_only"}
    candidate = None
    if args.split == "validation":
        if args.candidate is None:
            raise ValueError("Validation requires an already frozen candidate")
        candidate = json.loads(args.candidate.read_text())
        if candidate["fixture_sha256"] != digest(fixture_path) or candidate["product_source_sha256"] != sources:
            raise ValueError("Candidate identity differs from the frozen source and fixture")
        all_sources = {path.name: digest(path) for path in sorted(PACKAGE.glob("*.py"))}
        if (candidate["all_sdk_python_sha256"] != all_sources
                or candidate["evaluator_sha256"] != digest(Path(__file__))):
            raise ValueError("The frozen SDK or evaluation harness changed")
        args.ledger.mkdir(mode=0o700, parents=True, exist_ok=True)
        save(args.ledger / (digest(fixture_path) + "-validation-used.json"),
             {**registration, "candidate_sha256": digest(args.candidate), "status": "reserved"})
        registration["candidate_sha256"] = digest(args.candidate)
    args.output.mkdir(mode=0o700)
    save(args.output / "registration.json", registration)
    cohort = fixture["splits"][args.split]
    processor = ApprovedFixture(cohort["documents"])
    engine = (DevelopmentEngine(receipt["hindsight_url"], processor, integrated=True)
              if args.split == "development" else ValidationEngine(
                  receipt["hindsight_url"], processor, integrated=True,
                  floor=candidate["minimum_reranker_score"]))
    store = Store(receipt["dsn"], memory_engine=engine)
    await store.open()
    try:
        actual_data = await store.pool.fetchval("SHOW data_directory")
        if Path(actual_data).resolve() != Path(receipt["pg_data"]).resolve():
            raise ValueError("The selected database is not the owned synthetic cluster")
        account = await store.create_account("Synthetic search " + args.split)
        actor = await store.authenticate(account["token"])
        mapping = {}
        for index, document in enumerate(cohort["documents"], 1):
            op = Operation(op_id=uuid4(), memory_id=uuid4(), project="search-fixture", text=document["text"])
            await store.push(actor, [op])
            approved = await store.pool.fetchval(
                "SELECT text FROM am_collab.memories WHERE user_id=$1 AND id=$2 AND processing_state='ready'",
                actor.user_id, op.memory_id)
            if approved != document["text"]:
                raise ValueError("The preapproved source was not stored exactly")
            mapping[str(op.memory_id)] = document["id"]
            print(json.dumps({"indexed": index, "total": len(cohort["documents"])}), flush=True)
        floors = FLOORS if args.split == "development" else [candidate["minimum_reranker_score"]]
        by_floor = {str(floor): [] for floor in floors}
        for index, question in enumerate(cohort["queries"], 1):
            for floor in floors:
                if args.split == "development":
                    engine.floor = floor
                result = await store.search(actor, question["query"], project="search-fixture", limit=5)
                retrieved = sorted({mapping[source["id"]] for memory in result["memories"]
                                    for source in memory["sources"]})
                required, relevant = set(question["required_sources"]), set(question["relevant_sources"])
                row = {"id": question["id"], "cluster": question["cluster"], "kind": question["kind"],
                       "retrieved": retrieved, "required": sorted(required),
                       "any_hit": bool(required & set(retrieved)),
                       "all_evidence": bool(required) and required <= set(retrieved),
                       "noise": len(set(retrieved) - relevant),
                       "partial": result.get("partial", False)}
                by_floor[str(floor)].append(row)
            save(args.output / f"query-{index:03d}.json",
                 {floor: rows[-1] for floor, rows in by_floor.items()})
            save(args.output / f"native-{index:03d}.json", next(
                response for (path, query), response in engine.captured.items()
                if query == question["query"]))
            print(json.dumps({"queried": index, "total": len(cohort["queries"])}), flush=True)
        summary = {floor: metrics(rows) for floor, rows in by_floor.items()}
        eligible = [(float(floor), row) for floor, row in summary.items() if row["engineering_gate_pass"]]
        selected = max(eligible, key=lambda pair: (
            pair[1]["all_required_evidence_at_5"], pair[1]["any_hit_at_5"],
            -pair[1]["noise_sources"] / pair[1]["returned_sources"], pair[0]), default=None)
        report = {**registration, "metrics": summary,
                  "recommended_floor": selected[0] if selected else None,
                  "release_gate_status": "unknown_not_independent_release_evidence",
                  "uncertainty": "Wilson intervals describe this fixture only; bilingual queries share topic clusters"}
        save(args.output / "report.json", report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
    finally:
        await store.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--split", choices=["development", "validation"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--ledger", type=Path, default=Path.home() / ".local/state/am-search-evaluation")
    asyncio.run(main(parser.parse_args()))
