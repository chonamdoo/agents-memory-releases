#!/usr/bin/env python3
"""Offline real-environment audit, kept strict after publication. Never publishes or calls a provider."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

CHECKS = {
    "core_regression": ("현재 소스의 클라우드 핵심 회귀", 15),
    "answer_quality": ("정책·개발 답변 품질", 35),
    "admission_quality": ("저장 판단 품질", 10),
    "security": ("출처·프로젝트 범위·정정/삭제·민감정보", 15),
    "runtime_contract": ("실제 프로바이더와 Hindsight 통합", 10),
    "performance": ("입력·답변 지연과 사용량 예산", 5),
    "mac_install": ("맥북 설치·호스트·프로젝트 전환", 5),
    "distribution": ("정식 배포물·설치·복구 검증", 5),
}
PROFILES = ("personal", "company")
IDENTITY = ("candidate_id", "source_commit", "source_digest", "target_version", "hindsight_commit",
            "admission_patch_sha256", "platform")
SHARED = {"core_regression", "distribution"}
RUNTIME_CHECKS = {"retain_recall", "timestamp", "restart_durability", "retry_recovery", "delete"}
MAC_CHECKS = {"clean_install", "single_install_two_projects", "worktree_binding", "async_host_input",
              "login_restart", "upgrade_rollback"}
DIST_CHECKS = {"checksums", "licenses", "sbom", "clean_install_without_checkout", "rollback", "instructions"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parse_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    if len(raw) > 1048576:
        raise ValueError("oversized evidence")
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def read_json(path):
    return parse_json(path.read_bytes())


def profile_digest(candidate, profile):
    value = {"runtime": candidate["runtime_profile"], "profile": candidate["profiles"][profile]}
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                             separators=(",", ":")).encode())


def baseline_digest(candidate, profile):
    selected = candidate["profiles"][profile]
    value = {"upstream": candidate["hindsight_commit"], "runtime": candidate["runtime_profile"],
             **{k: selected[k] for k in ("host", "answer_model", "judge_model")}}
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                             separators=(",", ":")).encode())


def sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def num(value):
    return type(value) in (int, float) and 0 <= value <= 1e12 and math.isfinite(value)


def count(value):
    return type(value) is int and 0 <= value <= 1000000


def text(value):
    return isinstance(value, str) and bool(value.strip())


def checks(value, required):
    return isinstance(value, dict) and set(value) == required and all(v is True for v in value.values())


def valid_metrics(key, m, candidate, profile=None):
    if not isinstance(m, dict):
        return False
    if key == "core_regression":
        return (count(m.get("passed")) and m["passed"] >= 225 and
                count(m.get("phases_passed")) and m["phases_passed"] == 3 * m["passed"] and
                all(type(m.get(k)) is int and m[k] == 0 for k in ("failed", "skipped", "xfailed", "xpassed")) and
                m.get("complete") is True and m.get("source_digest_before") == candidate["source_digest"] and
                m.get("source_digest_after") == candidate["source_digest"] and sha(m.get("original_receipt_sha256")))
    if key == "distribution":
        assets = m.get("assets")
        return (checks(m.get("checks"), DIST_CHECKS) and m.get("artifact_version") == candidate["target_version"] and
                m.get("artifact_source_commit") == candidate["source_commit"] and
                m.get("prerelease") is False and m.get("draft") is False and
                m.get("platform") == candidate["platform"] and isinstance(assets, list) and bool(assets) and
                len({a.get("name") for a in assets if isinstance(a, dict)}) == len(assets) and
                all(isinstance(a, dict) and text(a.get("name")) and
                    re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", a["name"]) and sha(a.get("sha256")) and
                    type(a.get("bytes")) is int and a["bytes"] > 0 for a in assets))
    selected = candidate["profiles"][profile]
    role = "answer_model" if key in {"answer_quality", "performance"} else "admission_model"
    if (m.get("actual_provider") is not True or m.get("provider") != selected["provider"] or
            selected.get("host") not in {"codex", "claude", "omp"} or m.get("host") != selected["host"] or
            not text(selected.get("answer_model")) or not text(selected.get("admission_model")) or
            m.get("model") != selected[role] or m.get("profile_config_sha256") != profile_digest(candidate, profile)):
        return False
    if key == "answer_quality":
        fields = ("total", "answerable", "unknown", "correct", "baseline_correct", "unknown_correct",
                  "unsupported", "critical_regressions", "missing", "errors", "baseline_total",
                  "baseline_missing", "baseline_errors")
        return (all(count(m.get(k)) for k in fields) and m["total"] == 100 and
                m["answerable"] == 80 and m["unknown"] == 20 and 90 <= m["correct"] <= 100 and
                m["correct"] >= m["baseline_correct"] and m["baseline_correct"] <= 100 and
                19 <= m["unknown_correct"] <= 20 and m["unknown_correct"] <= m["correct"] <= 80 + m["unknown_correct"] and
                all(m[k] == 0 for k in ("unsupported", "critical_regressions", "missing", "errors")) and
                m["baseline_total"] == 100 and m["baseline_missing"] == m["baseline_errors"] == 0 and
                m.get("baseline_provider") == "hindsight-direct" and
                m.get("baseline_source_commit") == candidate["hindsight_commit"] and
                m.get("baseline_config_sha256") == baseline_digest(candidate, profile) and
                sha(m.get("baseline_answer_lock_sha256")) and m.get("baseline_first_answers_only") is True and
                sha(m.get("workload_sha256")) and m.get("baseline_workload_sha256") == m["workload_sha256"] and
                sha(m.get("dataset_sha256")) and sha(m.get("answer_lock_sha256")) and
                m.get("first_answers_only") is True and m.get("blind_grade") is True and
                m.get("baseline_model") == m["model"] and text(selected.get("judge_model")) and
                m.get("judge_model") == selected["judge_model"])
    if key == "admission_quality":
        return (all(count(m.get(k)) for k in ("durable", "kept", "temporary", "discarded", "unsafe", "blocked")) and
                m["durable"] == m["temporary"] == 20 and 18 <= m["kept"] <= 20 and
                19 <= m["discarded"] <= 20 and m["unsafe"] == m["blocked"] == 10 and
                sha(m.get("dataset_sha256")) and m.get("first_answers_only") is True)
    if key == "security":
        return (checks(m.get("checks"), {"provenance", "project_scope", "update_delete", "secrets_injection"}) and
                type(m.get("cases")) is int and m["cases"] >= 20 and
                type(m.get("violations")) is int and m["violations"] == 0 and m.get("actual_service") is True)
    if key == "runtime_contract":
        return checks(m.get("checks"), RUNTIME_CHECKS) and m.get("actual_service") is True
    if key == "mac_install":
        return (checks(m.get("checks"), MAC_CHECKS) and m.get("platform") == "Darwin-arm64" and
                m.get("actual_host") is True)
    if key == "performance":
        fields = ("capture_samples", "capture_p95_ms", "baseline_lookup_p95_ms", "candidate_lookup_p95_ms",
                  "answer_p95_ms", "observed_calls", "call_budget", "peak_memory_bytes")
        if not (all(num(m.get(k)) for k in fields) and
                all(count(m.get(k)) for k in ("capture_samples", "observed_calls", "call_budget")) and
                m["capture_samples"] >= 100 and
                m["capture_p95_ms"] <= 200 and m["baseline_lookup_p95_ms"] > 0 and
                m["candidate_lookup_p95_ms"] <= m["baseline_lookup_p95_ms"] + max(100, .1 * m["baseline_lookup_p95_ms"]) and
                m["answer_p95_ms"] <= 30000 and 0 < m["observed_calls"] <= m["call_budget"] and
                m["peak_memory_bytes"] > 0 and m.get("platform") == "Darwin-arm64" and
                m.get("budget_frozen_before_run") is True and m.get("cold_start_reported") is True):
            return False
        baseline, candidate_tokens = m.get("baseline_tokens"), m.get("candidate_tokens")
        if baseline is None and candidate_tokens is None:
            return profile == "company" and m.get("usage_unavailable") is True
        return num(baseline) and num(candidate_tokens) and baseline > 0 and candidate_tokens <= 1.1 * baseline
    return False


def safe_evidence(root, relative):
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(p in {"..", "."} for p in path.parts):
        raise ValueError("unsafe evidence path")
    current = root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("symlinked evidence")
    if not current.resolve().is_relative_to(root.resolve()):
        raise ValueError("outside candidate")
    return current


def evaluate(root):
    if root.is_symlink() or (root / "candidate.json").is_symlink():
        raise ValueError("symlinked candidate")
    c = read_json(root / "candidate.json")
    if (not isinstance(c, dict) or type(c.get("schema_version")) is not int or c["schema_version"] != 1 or
            not text(c.get("candidate_id")) or c.get("target_version") != "1.0.0" or
            c.get("platform") != "Darwin-arm64" or not sha(c.get("source_digest")) or
            c.get("release_prerelease") is not False or c.get("release_draft") is not False or
            c.get("source_repository") != "chonamdoo/agents-memory" or
            c.get("release_repository") != "chonamdoo/agents-memory-releases" or
            not isinstance(c.get("hindsight_commit"), str) or not re.fullmatch(r"[0-9a-f]{40}", c["hindsight_commit"]) or
            not sha(c.get("admission_patch_sha256")) or
            not isinstance(c.get("source_commit"), str) or not re.fullmatch(r"[0-9a-f]{40}", c["source_commit"]) or
            not isinstance(c.get("evidence"), dict) or set(c["evidence"]) != set(CHECKS) or
            not isinstance(c.get("profiles"), dict) or set(c["profiles"]) != set(PROFILES) or
            not all(isinstance(c["profiles"][p], dict) for p in PROFILES) or
            not all(set(c["profiles"][p]) == {"provider", "host", "answer_model", "admission_model", "judge_model"}
                    for p in PROFILES) or not isinstance(c.get("runtime_profile"), dict) or
            c["profiles"]["personal"].get("provider") != "jev" or
            c["profiles"]["company"].get("provider") != "subscription-cli"):
        raise ValueError("invalid candidate")
    rows, score = [], 0
    for key, (label, weight) in CHECKS.items():
        binding = c["evidence"][key]
        states = {p: "미검증" for p in PROFILES}
        if binding is not None:
            try:
                path = safe_evidence(root, binding["path"])
                raw = path.read_bytes()
                if not sha(binding["sha256"]) or digest(raw) != binding["sha256"]:
                    raise ValueError("evidence hash mismatch")
                receipt = parse_json(raw)
                if (not isinstance(receipt, dict) or
                        receipt.get("track") not in (None, "actual") or
                        any(receipt.get(k) != c[k] for k in IDENTITY)):
                    raise ValueError("stale candidate evidence")
                if key in SHARED:
                    passed = valid_metrics(key, receipt.get("metrics"), c)
                    states = dict.fromkeys(PROFILES, "통과" if passed else "미달")
                else:
                    if not isinstance(receipt.get("profiles"), dict) or set(receipt["profiles"]) != set(PROFILES):
                        raise ValueError("invalid profile matrix")
                    for profile in PROFILES:
                        metric = receipt["profiles"][profile]
                        if metric is not None:
                            states[profile] = "통과" if valid_metrics(key, metric, c, profile) else "미달"
            except (KeyError, OSError, TypeError, ValueError, OverflowError):
                states = dict.fromkeys(PROFILES, "증거 오류")
        earned = weight if all(v == "통과" for v in states.values()) else 0
        score += earned
        rows.append({"id": key, "label": label, "weight": weight, "earned": earned, **states})
    profile_scores = {p: sum(row["weight"] for row in rows if row[p] == "통과") for p in PROFILES}
    return {"candidate": c, "rows": rows, "score": score, "profile_scores": profile_scores,
            "maximum": sum(x[1] for x in CHECKS.values()),
            "ready": score == 100 and all(row[p] == "통과" for row in rows for p in PROFILES)}


def render(result):
    c = result["candidate"]
    lines = ["# 실환경 검증 점수표", "", "이 점수는 정답률이 아니라 **실환경 검증 완료 점수**다. "
             "미검증은 0점이며 품질 0%라는 뜻이 아니다. 가상 점수와 별도로 출시 후에도 100/100까지 확인한다.", "",
             f"후보: `{c['candidate_id']}` · 소스: `{c['source_commit']}`", "",
             "| 항목 | 배점 | 개인 Jev | 회사 구독 CLI | 획득 |", "| --- | ---: | --- | --- | ---: |"]
    for row in result["rows"]:
        lines.append(f"| {row['label']} | {row['weight']} | {row['personal']} | {row['company']} | {row['earned']} |")
    lines += ["", f"**공동 실환경 점수: {result['score']}/100 · 실환경 검증: {'완료' if result['ready'] else '미완료'}**",
              f"개인용 진행: {result['profile_scores']['personal']}/100 · 회사용 진행: {result['profile_scores']['company']}/100.", "",
              "정식 게시 여부는 [가상 출시 점수표](RELEASE-READINESS.ko.md)를 따른다. "
              "기준·종료 조건·이슈 이관: [출시 계약](README.ko.md). "
              "공통 회귀 결과는 한 번만 배점하며 과거 작은 QA/typed 대역 결과를 실제 프로필 품질로 세지 않는다.", ""]
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("check", "render"))
    p.add_argument("--candidate", type=Path,
                   default=Path(__file__).resolve().parents[1] / "release-candidates/v1.0.0")
    args = p.parse_args(argv)
    try:
        result = evaluate(args.candidate)
        if args.command == "render":
            print(render(result), end="")
            return 0
        print(json.dumps({"candidate_id": result["candidate"]["candidate_id"], "score": result["score"],
                          "maximum": result["maximum"], "profile_scores": result["profile_scores"], "ready": result["ready"],
                          "blocked": [r["id"] for r in result["rows"] if r["earned"] != r["weight"]]}))
        return 0 if result["ready"] else 3
    except (KeyError, OSError, TypeError, ValueError, OverflowError):
        print(json.dumps({"ready": False, "error": "INVALID_RELEASE_EVIDENCE"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
