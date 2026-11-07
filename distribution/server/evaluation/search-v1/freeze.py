"""Freeze a development-selected floor and the actual production source before validation."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from agents_memory_collab.memory_engine import HindsightEngine
from run import FLOORS, PACKAGE, ROOT, digest, save


class Probe(HindsightEngine):
    async def request(self, path, value=None, method=None):
        self.options = value
        return {"results": []}


async def main(args):
    report = json.loads(args.report.read_text())
    floor = report["recommended_floor"]
    if (report["split"] != "development" or floor not in FLOORS
            or not report["metrics"][str(floor)]["engineering_gate_pass"]
            or report["fixture_sha256"] != digest(ROOT / "fixture.json")):
        raise ValueError("No eligible development-selected candidate is available")
    processor = type("NeverCalledProcessor", (), {"contract": "agents-memory-grounded-v1"})()
    probe = Probe("http://127.0.0.1:1", processor, integrated=True)
    await probe.recall("synthetic-configuration-probe", "synthetic query")
    if probe.options["min_scores"] != {"reranker": floor}:
        raise ValueError("Apply the development-selected floor to production before freezing")
    artifacts = sorted(args.report.parent.glob("query-*.json"))
    if len(artifacts) != 52:
        raise ValueError("Development did not preserve every planned query artifact")
    candidate = {
        "schema": "frozen-search-candidate-v1",
        "fixture_sha256": report["fixture_sha256"],
        "minimum_reranker_score": floor,
        "product_source_sha256": {name: digest(PACKAGE / name) for name in (
            "memory_engine.py", "store.py", "stdio.py")},
        "all_sdk_python_sha256": {path.name: digest(path) for path in sorted(PACKAGE.glob("*.py"))},
        "evaluator_sha256": digest(ROOT / "run.py"),
        "development_report_sha256": digest(args.report),
        "development_query_sha256": {path.name: digest(path) for path in artifacts},
        "annotation": report["annotation"],
        "external_jev_api_calls": 0,
        "validation_outputs_seen": False,
    }
    save(args.output, candidate)
    print(json.dumps({"candidate": str(args.output), "sha256": digest(args.output), "floor": floor}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(main(parser.parse_args()))
