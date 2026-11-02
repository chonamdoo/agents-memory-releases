"""Synthetic gate tests only; their receipts must never enter the real scorecard."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import stable_release_gate as gate

ROOT = Path(__file__).resolve().parents[1]


class StableGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.c = copy.deepcopy(gate.evaluate(ROOT / "release-candidates/v1.0.0")["candidate"])
        self.c["candidate_id"] = "SYNTHETIC-TEST-ONLY"
        self.c["evidence"] = dict.fromkeys(gate.CHECKS)
        for profile in gate.PROFILES:
            self.c["profiles"][profile].update(host="codex", answer_model="synthetic-test-model",
                                              admission_model="synthetic-test-model", judge_model="synthetic-judge")
        self.save()

    def save(self):
        (self.root / "candidate.json").write_text(json.dumps(self.c))

    def metrics(self, key, profile):
        base = {"actual_provider": True, "provider": self.c["profiles"][profile]["provider"],
                "model": "synthetic-test-model", "host": "codex",
                "profile_config_sha256": gate.profile_digest(self.c, profile)}
        if key == "core_regression":
            return {"passed": 225, "phases_passed": 675, "failed": 0, "skipped": 0, "xfailed": 0,
                    "xpassed": 0, "complete": True, "source_digest_before": self.c["source_digest"],
                    "source_digest_after": self.c["source_digest"], "original_receipt_sha256": "a" * 64}
        if key == "distribution":
            return {"checks": dict.fromkeys(gate.DIST_CHECKS, True), "artifact_version": "1.0.0",
                    "artifact_source_commit": self.c["source_commit"], "prerelease": False, "draft": False,
                    "platform": "Darwin-arm64", "assets": [{"name": "synthetic.tar.gz", "sha256": "a" * 64, "bytes": 1}]}
        if key == "answer_quality":
            return base | {"total": 100, "answerable": 80, "unknown": 20, "correct": 95,
                           "baseline_correct": 94, "unknown_correct": 20, "unsupported": 0,
                           "critical_regressions": 0, "missing": 0, "errors": 0, "dataset_sha256": "a" * 64,
                           "answer_lock_sha256": "b" * 64, "first_answers_only": True, "blind_grade": True,
                           "baseline_model": base["model"], "judge_model": "synthetic-judge",
                           "baseline_total": 100, "baseline_missing": 0, "baseline_errors": 0,
                           "baseline_provider": "hindsight-direct", "baseline_source_commit": self.c["hindsight_commit"],
                           "baseline_config_sha256": gate.baseline_digest(self.c, profile),
                           "baseline_answer_lock_sha256": "c" * 64, "baseline_first_answers_only": True,
                           "workload_sha256": "d" * 64, "baseline_workload_sha256": "d" * 64}
        if key == "admission_quality":
            return base | {"durable": 20, "kept": 18, "temporary": 20, "discarded": 19,
                           "unsafe": 10, "blocked": 10, "dataset_sha256": "a" * 64, "first_answers_only": True}
        if key == "security":
            return base | {"checks": dict.fromkeys({"provenance", "project_scope", "update_delete", "secrets_injection"}, True),
                           "cases": 20, "violations": 0, "actual_service": True}
        if key == "runtime_contract":
            return base | {"checks": dict.fromkeys(gate.RUNTIME_CHECKS, True), "actual_service": True}
        if key == "mac_install":
            return base | {"checks": dict.fromkeys(gate.MAC_CHECKS, True), "platform": "Darwin-arm64", "actual_host": True}
        if key == "performance":
            return base | {"capture_samples": 100, "capture_p95_ms": 150, "baseline_lookup_p95_ms": 500,
                           "candidate_lookup_p95_ms": 550, "answer_p95_ms": 10000, "observed_calls": 100,
                           "call_budget": 100, "peak_memory_bytes": 1000, "platform": "Darwin-arm64",
                           "budget_frozen_before_run": True, "cold_start_reported": True,
                           "baseline_tokens": 10000, "candidate_tokens": 10000}
        self.fail(key)

    def receipt(self, key):
        value = {k: self.c[k] for k in gate.IDENTITY}
        if key in gate.SHARED:
            value["metrics"] = self.metrics(key, "personal")
        else:
            value["profiles"] = {p: self.metrics(key, p) for p in gate.PROFILES}
        return value

    def attach(self, key, receipt=None):
        path = self.root / (key + ".json")
        path.write_text(json.dumps(self.receipt(key) if receipt is None else receipt))
        self.c["evidence"][key] = {"path": path.name, "sha256": gate.digest(path.read_bytes())}
        self.save()

    def all_pass(self):
        for key in gate.CHECKS:
            self.attach(key)

    def test_partial_matrix_only_earns_core_points(self):
        self.attach("core_regression")
        result = gate.evaluate(self.root)
        self.assertEqual(result["score"], 15)
        self.assertFalse(result["ready"])

    def test_generated_public_table_matches_receipts(self):
        expected = gate.render(gate.evaluate(ROOT / "release-candidates/v1.0.0"))
        self.assertEqual((ROOT / "release-candidates/v1.0.0/SCORECARD.ko.md").read_text(), expected)

    def test_synthetic_full_matrix_needs_all_eight_categories(self):
        self.all_pass()
        self.assertTrue(gate.evaluate(self.root)["ready"])
        self.c["evidence"]["mac_install"] = None
        self.save()
        self.assertFalse(gate.evaluate(self.root)["ready"])

    def test_one_profile_cannot_pass_for_the_other(self):
        self.all_pass()
        value = self.receipt("answer_quality")
        value["profiles"]["company"] = None
        self.attach("answer_quality", value)
        result = gate.evaluate(self.root)
        self.assertEqual(result["score"], 65)
        self.assertFalse(result["ready"])

    def test_qa_cannot_replace_fixed_denominator_or_hide_errors(self):
        for field, value in [("total", 8), ("unknown_correct", 18), ("missing", 1), ("errors", 1),
                             ("baseline_correct", 96), ("unsupported", 1), ("critical_regressions", 1),
                             ("actual_provider", False), ("blind_grade", "true"), ("correct", True)]:
            with self.subTest(field=field):
                metric = self.metrics("answer_quality", "personal")
                metric[field] = value
                self.assertFalse(gate.valid_metrics("answer_quality", metric, self.c, "personal"))

    def test_qa_impossible_counts_reject(self):
        metric = self.metrics("answer_quality", "personal") | {"correct": 100, "unknown_correct": 19}
        self.assertFalse(gate.valid_metrics("answer_quality", metric, self.c, "personal"))

    def test_baseline_must_be_complete_frozen_and_same_workload(self):
        for field, value in [("baseline_total", 8), ("baseline_missing", 1), ("baseline_errors", 1),
                             ("baseline_provider", "not-official"), ("baseline_source_commit", "0" * 40),
                             ("baseline_config_sha256", "a" * 64), ("baseline_answer_lock_sha256", None),
                             ("baseline_workload_sha256", "e" * 64), ("baseline_first_answers_only", False)]:
            with self.subTest(field=field):
                metric = self.metrics("answer_quality", "personal")
                metric[field] = value
                self.assertFalse(gate.valid_metrics("answer_quality", metric, self.c, "personal"))

    def test_unsafe_admission_and_mock_runtime_reject(self):
        metric = self.metrics("admission_quality", "personal") | {"blocked": 9}
        self.assertFalse(gate.valid_metrics("admission_quality", metric, self.c, "personal"))
        metric = self.metrics("runtime_contract", "personal") | {"actual_service": False}
        self.assertFalse(gate.valid_metrics("runtime_contract", metric, self.c, "personal"))

    def test_only_mac_host_evidence_counts(self):
        metric = self.metrics("mac_install", "company") | {"platform": "Linux-x86_64"}
        self.assertFalse(gate.valid_metrics("mac_install", metric, self.c, "company"))

    def test_all_candidate_identity_fields_bind_receipts(self):
        for field in gate.IDENTITY:
            with self.subTest(field=field):
                value = self.receipt("core_regression")
                value[field] = "stale"
                self.attach("core_regression", value)
                self.assertEqual(gate.evaluate(self.root)["score"], 0)

    def test_model_host_and_runtime_changes_invalidate_old_receipts(self):
        for field, value in [("answer_model", "different-model"), ("admission_model", "different-admitter"),
                             ("host", "claude"), ("judge_model", "different-judge")]:
            with self.subTest(field=field):
                self.all_pass()
                before = copy.deepcopy(self.c)
                self.c["profiles"]["company"][field] = value
                self.save()
                self.assertFalse(gate.evaluate(self.root)["ready"])
                self.c = before
        self.all_pass()
        self.c["runtime_profile"]["retain_chunk_size"] = 800
        self.save()
        self.assertFalse(gate.evaluate(self.root)["ready"])

    def test_only_the_bytes_actually_hashed_are_evaluated(self):
        self.all_pass()
        bad = self.receipt("answer_quality")
        bad["profiles"]["personal"]["correct"] = 0
        self.attach("answer_quality", bad)
        replacement = json.dumps(self.receipt("answer_quality")).encode()
        original = Path.read_bytes
        reads = []

        def read(path):
            if path == self.root / "answer_quality.json":
                reads.append(1)
                if len(reads) > 1:
                    return replacement
            return original(path)

        with patch.object(Path, "read_bytes", read):
            result = gate.evaluate(self.root)
        self.assertEqual(len(reads), 1)
        self.assertFalse(result["ready"])

    def test_tampered_missing_and_symlink_evidence_cannot_pass(self):
        self.attach("core_regression")
        path = self.root / "core_regression.json"
        path.write_text("{}")
        self.assertEqual(gate.evaluate(self.root)["score"], 0)
        path.unlink()
        self.assertEqual(gate.evaluate(self.root)["score"], 0)
        other = self.root / "other.json"
        other.write_text(json.dumps(self.receipt("core_regression")))
        path.symlink_to(other)
        self.c["evidence"]["core_regression"]["sha256"] = gate.digest(other.read_bytes())
        self.save()
        self.assertEqual(gate.evaluate(self.root)["score"], 0)

    def test_evidence_cannot_escape_candidate_directory(self):
        self.c["evidence"]["core_regression"] = {"path": "../outside.json", "sha256": "a" * 64}
        self.save()
        self.assertEqual(gate.evaluate(self.root)["score"], 0)

    def test_nonfinite_and_wrong_json_shapes_fail_closed(self):
        for value in [[], None, {"schema_version": True}]:
            (self.root / "candidate.json").write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                gate.evaluate(self.root)
        for raw in ['{"x":1,"x":2}', '{"x":NaN}']:
            (self.root / "bad.json").write_text(raw)
            with self.assertRaises(ValueError):
                gate.read_json(self.root / "bad.json")

    def test_precise_budget_and_finite_numbers_required(self):
        for field, value in [("capture_p95_ms", 201), ("capture_p95_ms", float("nan")),
                             ("capture_samples", 99), ("observed_calls", 101),
                             ("candidate_tokens", 11001), ("answer_p95_ms", 30001),
                             ("capture_samples", 100.5), ("observed_calls", .1)]:
            with self.subTest(field=field):
                metric = self.metrics("performance", "personal")
                metric[field] = value
                self.assertFalse(gate.valid_metrics("performance", metric, self.c, "personal"))

    def test_company_unavailable_usage_is_not_fake_zero_cost(self):
        metric = self.metrics("performance", "company") | {"baseline_tokens": None,
                  "candidate_tokens": None, "usage_unavailable": True}
        self.assertTrue(gate.valid_metrics("performance", metric, self.c, "company"))
        self.assertFalse(gate.valid_metrics("performance", metric, self.c, "personal"))

    def test_no_old_or_prerelease_artifact_can_pass(self):
        for field, value in [("artifact_version", "0.1.0"), ("prerelease", True),
                             ("draft", True), ("artifact_source_commit", "0" * 40), ("assets", [])]:
            with self.subTest(field=field):
                metric = self.metrics("distribution", "personal")
                metric[field] = value
                self.assertFalse(gate.valid_metrics("distribution", metric, self.c))

    def test_candidate_preview_flags_cannot_be_stable(self):
        for field in ["release_prerelease", "release_draft"]:
            self.c[field] = True
            self.save()
            with self.assertRaises(ValueError):
                gate.evaluate(self.root)
            self.c[field] = False

    def test_cli_blocked_is_nonzero_and_does_not_publish(self):
        run = subprocess.run([sys.executable, str(ROOT / "tools/stable_release_gate.py"), "check",
                              "--candidate", str(self.root)],
                             capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 3)
        self.assertIs(json.loads(run.stdout)["ready"], False)


if __name__ == "__main__":
    unittest.main()
