#!/usr/bin/env python3
"""Check exported offline receipts; does not authenticate execution or approve GA."""
import hashlib
import json
import sys
from pathlib import Path


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def verify(root):
    manifest = json.loads((root / "NATIVE-LIFECYCLE.json").read_text())
    require(manifest.get("schema") in {"agents-memory-offline-native-lifecycle-v1",
                                       "agents-memory-offline-native-lifecycle-v2"}, "manifest_schema")
    installed_prefix = None
    if manifest["schema"] == "agents-memory-offline-native-lifecycle-v2":
        verification = root.parent / "v2.0.0-jev197" / "VERIFICATION.json"
        raw = verification.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == manifest["runtime_verification_sha256"],
                "runtime_verification_hash")
        candidate = json.loads(raw)
        require(manifest["candidate"]["archive_sha256"] == candidate["archive"]["sha256"]
                and manifest["candidate"]["sdk_wheel_sha256"] == candidate["sdk_wheel_sha256"]
                and manifest["candidate"]["core_cp312_wheel_sha256"] == candidate["core_wheels"]["cp312"]["sha256"],
                "final_candidate_wheel_identity")
        binding = manifest["installed_wheels"]
        name = Path(binding["path"])
        require(len(name.parts) == 1 and name.suffix == ".json", "installed_identity_path")
        raw = (root / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == binding["sha256"], "installed_identity_hash")
        installed = json.loads(raw)
        require(installed["installed_prefix_verified"] is True
                and installed["external_network"] == "none", "installed_identity_scope")
        core = "agents_memory_core-2.0.0-cp312-none-any.whl"
        sdk = "agents_memory_collaboration-2.0.0-py3-none-any.whl"
        require(installed[core + "_sha256"] == candidate["core_wheels"]["cp312"]["sha256"]
                and installed[sdk + "_sha256"] == candidate["sdk_wheel_sha256"]
                and installed["module_counts"] == {core: 13, sdk: 16}, "installed_wheel_bytes")
        installed_prefix = binding["prefix"]
        require(isinstance(installed_prefix, str) and Path(installed_prefix).is_absolute(),
                "installed_prefix")
    expected = manifest["case_ids"]
    require(len(expected) == len(set(expected)) == 36, "fixed_case_census")
    require(set(manifest["hosts"]) == {"claude", "codex", "omp"}, "host_census")
    global_markers, global_sessions, counts = set(), set(), {}
    for host, row in manifest["hosts"].items():
        seen, sessions = [], set()
        for receipt in row["receipts"]:
            path = Path(receipt["path"])
            require(len(path.parts) == 1 and path.suffix == ".json", "receipt_path")
            raw = (root / path).read_bytes()
            require(hashlib.sha256(raw).hexdigest() == receipt["sha256"], "receipt_hash")
            data = json.loads(raw)
            require(data["passed"] is True and data["blockers"] == [], "failed_receipt")
            report, evidence = data["report_data"], data["evidence"]
            require(report["readiness_scope"] == "offline_native_lifecycle_only", "scope")
            require(report["selected_real_provider_compliance"] == "unverified", "real_provider_claim")
            require(report["human_authorship"] == "unverified", "authorship_claim")
            require(report["case_manifest"]["sha256"] == manifest["cases_sha256"], "case_identity")
            require(report["case_manifest"]["corpus_case_ids"] == expected, "case_order")
            require(len(report["hosts"]) == 1 and report["hosts"][0]["host"] == host, "receipt_host")
            control = report["execution_controls"]
            require(control["memory_max_bytes"] == 4 * 1024**3 and control["memory_swap_max_bytes"] == 0,
                    "memory_limits")
            require(control["cpu_quota"] / control["cpu_period"] == 2 and control["pids_max"] == 256,
                    "cpu_pids_limits")
            require(control["network_interfaces"] == ["lo"] and control["root_readonly"] is True
                    and control["source_and_tools_readonly"] is True
                    and control["nonroot_no_capabilities_no_new_privileges"] is True, "isolation")
            require(control["http_request_limit"] == 128 and report["requests"] <= 128, "request_limit")
            require(report["installed_runtime"]["isolated"] is True, "installed_runtime")
            if installed_prefix is not None:
                runtime = report["installed_runtime"]
                require(runtime["prefix"] == installed_prefix
                        and runtime["executable"] == str(Path(installed_prefix) / "bin/python"),
                        "final_installed_runtime_prefix")
                require(set(runtime["packages"]) == {"agents_memory", "agents_memory_collab"}
                        and all(Path(package["origin"]).is_relative_to(installed_prefix)
                                and ".." not in Path(package["origin"]).parts
                                for package in runtime["packages"].values()),
                        "final_installed_package_origin")
            require(all(p["version"] == "2.0.0" for p in report["installed_runtime"]["packages"].values()),
                    "installed_versions")
            cases = report["hosts"][0]["cases"]
            require([case["case_id"] for case in cases] == report["planned_case_ids_per_host"], "batch_census")
            require(len(evidence["phases"]) == 3 * len(cases), "phase_census")
            for case in cases:
                cid, project = case["case_id"], case["project"]
                require(cid in expected and case["host"] == host, "unexpected_case")
                require(case["stable_fact_survived_compaction"] is True
                        and case["independent_project_status"] is True, "case_proof")
                session_ids = set(case["session_sha256"])
                require(session_ids and not session_ids & (sessions | global_sessions), "session_collision")
                sessions.update(session_ids)
                seen.append(cid)
                phases = [phase for phase in evidence["phases"] if phase["project"] == project]
                require([phase["phase"] for phase in phases] == ["startup", "resume", "compact"], "phase_order")
                for phase in phases:
                    require(phase["native_hook"] is True and phase["provider_ingress"] is True
                            and phase["stable_fact_at_ingress"] is True, "phase_proof")
                    require(set(phase["session_sha256"]) == session_ids, "phase_session")
                    require(len(phase["marker"]) == 1, "phase_marker_count")
                    marker = phase["marker"][0]
                    require(marker not in global_markers, "marker_collision")
                    global_markers.add(marker)
                    event = ({"startup": "session_start", "resume": "session_switch", "compact": "session_compact"}
                             [phase["phase"]] if host == "omp" else "SessionStart")
                    source = "resume" if host == "omp" and phase["phase"] == "resume" else (
                        None if host == "omp" else phase["phase"])
                    require(any(hook.get("event") == event and hook.get("source") == source
                                and hook.get("sdk_returncode") == 0 and marker in hook.get("markers", [])
                                and hook.get("session_sha256") in session_ids
                                for hook in evidence["native_hooks"][project]), "native_hook_join")
                    require(any(marker in ingress["input_markers"] and ingress["stable_fact_case_ids"] == [cid]
                                for ingress in evidence["provider_ingress"]), "marker_fact_join")
                    if phase["phase"] == "compact":
                        require(phase["post_compaction_continuation"] is True, "compact_continuation")
                if host == "codex":
                    require(any(item["project"] == project and item["status"] == "completed"
                                and item["thread_sha256"] in session_ids
                                for item in evidence["codex_compactions"]), "codex_compact_completion")
            if host == "codex":
                require(len(evidence["codex_compactions"]) == len(cases), "codex_compaction_census")
        require(len(seen) == 36 and len(set(seen)) == 36 and set(seen) == set(expected), "host_case_census")
        global_sessions.update(sessions)
        require(row["successes"] == row["denominator"] == 36, "reported_statistics")
        lower = 1 / (1 + 1.959963984540054**2 / 36)
        require(abs(row["wilson95_lower"] - lower) < 1e-12 and lower >= 0.90, "wilson_statistics")
        counts[host] = len(seen)
    return counts


if __name__ == "__main__":
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
    try:
        print(json.dumps({"verified_offline_case_counts": verify(directory),
                          "stable_release_approval": False}, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("Evidence rejected: " + str(error), file=sys.stderr)
        raise SystemExit(1)
