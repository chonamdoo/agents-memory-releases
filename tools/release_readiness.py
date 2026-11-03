#!/usr/bin/env python3
"""Separate virtual release readiness from the unchanged real-environment audit. Never publishes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import stable_release_gate as actual

VIRTUAL = {
    "core_regression": ("고정 소스 회귀", 20),
    "provider_contract": ("개인·회사 모델 응답 대역 계약", 20),
    "service_lifecycle": ("공통 서비스·프로필 대역의 결합 검증", 20),
    "security": ("대역 모델 경로의 안전·출처", 20),
    "virtual_install": ("격리 환경 설치·업그레이드·복구", 10),
    "distribution": ("최종 배포물·해시·라이선스·설치", 10),
}
SHARED = {"core_regression", "distribution"}
INSTALL = {"clean_install", "isolated_process", "installed_version", "two_projects", "upgrade_rollback", "config_preserved"}
SAFETY = {"provenance", "project_scope", "update_delete", "secrets_injection"}
KINDS = {"core_regression": "source_tests", "provider_contract": "model_output_double",
         "service_lifecycle": "service_with_model_double", "security": "service_with_model_double",
         "virtual_install": "isolated_install", "distribution": "final_artifact_validation"}


def valid(key, metric, candidate):
    if not isinstance(metric, dict):
        return False
    if key == "core_regression":
        return actual.valid_metrics(key, metric, candidate)
    if key == "distribution":
        return (actual.valid_metrics(key, metric, candidate) and metric.get("private_source_published") is False and
                metric.get("private_core_excluded") is True and actual.sha(metric.get("artifact_inspection_sha256")))
    if key == "provider_contract":
        return (all(actual.count(metric.get(k)) for k in ("cases", "passed", "failed")) and
                metric["cases"] == metric["passed"] == 50 and metric["failed"] == 0 and
                actual.sha(metric.get("case_manifest_sha256")) and metric.get("model_output_double") is True and
                metric.get("semantic_quality_tested") is False and
                actual.checks(metric.get("checks"), {"keep_discard_review", "invalid_fail_closed", "no_fallback", "source_preserved"}))
    if key == "service_lifecycle":
        return (actual.checks(metric.get("checks"), actual.RUNTIME_CHECKS) and
                metric.get("real_service") is True and metric.get("model_output_double") is True and
                metric.get("all_generated_parts_deleted") is True and
                metric.get("validation_method") == "common_service_plus_mode_double" and
                actual.sha(metric.get("common_runtime_result_sha256")) and
                actual.sha(metric.get("profile_service_result_sha256")))
    if key == "security":
        return (actual.count(metric.get("cases")) and metric["cases"] >= 20 and
                type(metric.get("violations")) is int and metric["violations"] == 0 and
                actual.checks(metric.get("checks"), SAFETY) and metric.get("real_service") is True and
                metric.get("model_output_double") is True)
    if key == "virtual_install":
        return actual.checks(metric.get("checks"), INSTALL) and metric.get("version") == candidate["target_version"]
    return False


def composed_service(root, metric, profile, candidate, virtual):
    common = metric.get("common_runtime_binding")
    specific = metric.get("profile_service_binding")
    if (common != candidate["evidence"]["runtime_contract"] or common is None or
            specific != virtual["evidence"]["security"] or specific is None):
        return False
    def read(binding):
        path = actual.safe_evidence(root, binding["path"])
        raw = path.read_bytes()
        if not actual.sha(binding["sha256"]) or actual.digest(raw) != binding["sha256"]:
            raise ValueError("invalid composed evidence hash")
        receipt = actual.parse_json(raw)
        if not isinstance(receipt, dict) or any(receipt.get(k) != candidate[k] for k in actual.IDENTITY):
            raise ValueError("stale composed evidence")
        return receipt
    common_receipt, specific_receipt = read(common), read(specific)
    common_matrix, specific_matrix = common_receipt.get("profiles"), specific_receipt.get("profiles")
    if (not isinstance(common_matrix, dict) or not isinstance(specific_matrix, dict) or
            set(common_matrix) != set(actual.PROFILES) or set(specific_matrix) != set(actual.PROFILES)):
        return False
    common_metric = common_matrix.get("personal")
    specific_metric = specific_matrix.get(profile)
    return (common_receipt.get("track") in (None, "actual") and
            actual.valid_metrics("runtime_contract", common_metric, candidate, "personal") and
            common_receipt.get("execution_result_sha256") == metric["common_runtime_result_sha256"] and
            specific_receipt.get("track") == "virtual" and
            specific_receipt.get("execution_kind") == KINDS["security"] and
            specific_receipt.get("execution_platform") == virtual["execution_platform"] and
            specific_receipt.get("model_quality_claim") is False and
            specific_receipt.get("execution_result_sha256") == metric["profile_service_result_sha256"] and
            isinstance(specific_metric, dict) and specific_metric.get("target_profile") == profile and
            specific_metric.get("profile_config_sha256") == actual.profile_digest(candidate, profile) and
            valid("security", specific_metric, candidate))


def evaluate(root):
    real = actual.evaluate(root)
    c = real["candidate"]
    if (root / "release-policy.json").is_symlink() or (root / "virtual-candidate.json").is_symlink():
        raise ValueError("symlinked policy")
    policy = actual.read_json(root / "release-policy.json")
    if (not isinstance(policy, dict) or type(policy.get("schema_version")) is not int or
            type(policy.get("required_virtual_score")) is not int or
            any(type(policy.get(k)) is not bool for k in ("prerelease", "draft")) or
            policy != {"schema_version": 1, "release_gate": "virtual", "required_virtual_score": 100,
                  "actual_verification": "after_release", "publication": "stable", "prerelease": False, "draft": False}):
        raise ValueError("invalid release policy")
    v = actual.read_json(root / "virtual-candidate.json")
    if (not isinstance(v, dict) or type(v.get("schema_version")) is not int or v["schema_version"] != 1 or
            v.get("track") != "virtual" or v.get("execution_platform") != "Linux-x86_64" or
            v.get("model_quality_claim") is not False or
            any(v.get(k) != c[k] for k in actual.IDENTITY) or
            not isinstance(v.get("evidence"), dict) or set(v["evidence"]) != set(VIRTUAL)):
        raise ValueError("invalid virtual candidate")
    rows = []
    for key, (label, weight) in VIRTUAL.items():
        states = dict.fromkeys(actual.PROFILES, "미검증")
        binding = v["evidence"][key]
        if binding is not None:
            try:
                path = actual.safe_evidence(root, binding["path"])
                raw = path.read_bytes()
                if not actual.sha(binding["sha256"]) or actual.digest(raw) != binding["sha256"]:
                    raise ValueError("hash mismatch")
                receipt = actual.parse_json(raw)
                if (not isinstance(receipt, dict) or receipt.get("track") != "virtual" or
                        receipt.get("execution_kind") != KINDS[key] or
                        receipt.get("execution_platform") != v["execution_platform"] or
                        receipt.get("model_quality_claim") is not False or
                        not actual.sha(receipt.get("execution_result_sha256")) or
                        any(receipt.get(k) != c[k] for k in actual.IDENTITY)):
                    raise ValueError("wrong evidence track or identity")
                if key in SHARED:
                    ok = valid(key, receipt.get("metrics"), c)
                    states = dict.fromkeys(actual.PROFILES, "통과" if ok else "미달")
                else:
                    matrix = receipt.get("profiles")
                    if not isinstance(matrix, dict) or set(matrix) != set(actual.PROFILES):
                        raise ValueError("wrong matrix")
                    for profile in actual.PROFILES:
                        m = matrix[profile]
                        if m is not None:
                            ok = (isinstance(m, dict) and m.get("target_profile") == profile and
                                  m.get("profile_config_sha256") == actual.profile_digest(c, profile) and valid(key, m, c))
                            if ok and key == "service_lifecycle":
                                ok = composed_service(root, m, profile, c, v)
                            states[profile] = "통과" if ok else "미달"
            except (KeyError, OSError, TypeError, ValueError, OverflowError):
                states = dict.fromkeys(actual.PROFILES, "증거 오류")
        earned = weight if all(x == "통과" for x in states.values()) else 0
        rows.append({"id": key, "label": label, "weight": weight, "earned": earned, **states})
    score = sum(x["earned"] for x in rows)
    return {"candidate": c, "virtual": {"score": score, "maximum": 100, "ready": score == 100, "rows": rows,
            "profile_scores": {p: sum(x["weight"] for x in rows if x[p] == "통과") for p in actual.PROFILES}},
            "actual": real, "release_ready": score == 100}


def render(result):
    v, a = result["virtual"], result["actual"]
    lines = ["# 가상 출시 검증과 실환경 검증", "",
             "가상 100/100이면 정식 v1.0.0을 게시하고 실환경 검증을 이어간다. "
             "모델 대역의 기능 시험은 실제 모델 품질·Mac·계정·클라우드 운영 검증을 뜻하지 않는다.", "",
             "| 가상 출시 항목 | 배점 | 개인 대역 | 회사 대역 | 획득 |", "| --- | ---: | --- | --- | ---: |"]
    for row in v["rows"]:
        lines.append(f"| {row['label']} | {row['weight']} | {row['personal']} | {row['company']} | {row['earned']} |")
    lines += ["", f"**가상 출시 점수: {v['score']}/100 · 정식 게시: {'가능' if result['release_ready'] else '대기'}**", "",
              f"실환경: 개인 {a['profile_scores']['personal']}/100 · 회사 {a['profile_scores']['company']}/100 · "
              f"공동 {a['score']}/100. 실환경 검증은 출시 뒤 계속한다.", "",
              "[실환경 세부표](SCORECARD.ko.md) · [출시 정책](README.ko.md). "
              "최종 배포물 검증을 생략하거나 가상 점수를 실제 QA/SOTA 점수로 표시하지 않는다.", ""]
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("check", "render"))
    p.add_argument("--track", choices=("virtual", "actual"), default="virtual")
    p.add_argument("--candidate", type=Path, default=Path(__file__).resolve().parents[1] / "release-candidates/v1.0.0")
    args = p.parse_args(argv)
    try:
        result = evaluate(args.candidate)
        if args.command == "render":
            print(render(result), end="")
            return 0
        track = result[args.track]
        print(json.dumps({"track": args.track, "score": track["score"], "maximum": 100,
                          "profile_scores": track["profile_scores"], "ready": track["ready"],
                          "release_ready": result["release_ready"], "actual_complete": result["actual"]["ready"]}))
        return 0 if track["ready"] else 3
    except (KeyError, OSError, TypeError, ValueError, OverflowError):
        print(json.dumps({"release_ready": False, "error": "INVALID_RELEASE_EVIDENCE"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
