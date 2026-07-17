#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.cwd()
MAINBASE = Path(os.environ.get("MAINBASE", str(Path.home() / "work/grt_work/audio_engineering_repo_skeleton_v1")))
JAVA = Path(os.environ.get("JAVA", str(Path.home() / "work/grt_work/media-task-platform-java")))
CLOUD = Path(os.environ.get("CLOUD", str(ROOT)))

OUT_JSON = ROOT / "loadtest/reports/week17_layer_mix_v0_observability_evidence_index.json"
OUT_PROM = ROOT / "observability/prometheus/week17_layer_mix_v0_observability_evidence_index.prom"
OUT_RUNBOOK = ROOT / "docs/runbooks/week17-layer-mix-v0-observability-evidence-index.md"
LOG_DIR = ROOT / "artifacts/logs"

EXPECTED_CLOUD_GENERATED_FILES = {
    "scripts/build_week17_layer_mix_v0_observability_evidence_index.py",
    "loadtest/reports/week17_layer_mix_v0_observability_evidence_index.json",
    "observability/prometheus/week17_layer_mix_v0_observability_evidence_index.prom",
    "docs/runbooks/week17-layer-mix-v0-observability-evidence-index.md",
}

INPUTS = {
    "mainbase_layer_mix_manifest": MAINBASE / "artifacts/evals/week17_layer_mix_v0_manifest.json",
    "mainbase_layer_mix_wav": MAINBASE / "artifacts/audio/week17_layer_mix_v0/week17_layer_mix_v0_placeholder_control_mix.wav",
    "java_result_preview_report": JAVA / "artifacts/manifests/week17_layer_mix_v0_result_preview_api_report.json",
    "java_result_preview_payload": JAVA / "artifacts/manifests/week17_layer_mix_v0_result_mainbase_payload.json",
    "cloud_result_platform_preview": ROOT / "loadtest/reports/week17_layer_mix_v0_result_platform_preview.json",
    "cloud_action_gate_report": ROOT / "loadtest/reports/week17_layer_mix_v0_action_gate.json",
    "cloud_alert_rules_report": ROOT / "loadtest/reports/week17_layer_mix_v0_action_gate_alert_rules_report.json",
    "cloud_alert_semantic_fallback_report": ROOT / "loadtest/reports/week17_layer_mix_v0_action_gate_alert_rules_semantic_fallback_report.json",
    "cloud_alert_semantic_fallback_metrics_report": ROOT / "loadtest/reports/week17_layer_mix_v0_alert_semantic_fallback_metrics_report.json",
    "cloud_alert_semantic_fallback_metrics_prom": ROOT / "observability/prometheus/week17_layer_mix_v0_action_gate_alert_semantic_fallback.prom",
    "cloud_action_gate_metrics_prom": ROOT / "observability/prometheus/week17_layer_mix_v0_action_gate.prom",
    "cloud_official_promtool_report_optional": ROOT / "loadtest/reports/week17_layer_mix_v0_alert_promtool_official_report.json",
}


def run(cmd: list[str], cwd: Path) -> str:
    try:
        return subprocess.check_output(cmd, cwd=str(cwd), text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:
        return f"ERROR:{exc}"


def git_summary(repo: Path) -> dict[str, Any]:
    if not (repo / ".git").exists():
        return {
            "path": str(repo),
            "exists": repo.exists(),
            "isGitRepo": False,
            "head": None,
            "originMain": None,
            "aheadBehind": None,
            "porcelainCount": None,
            "clean": False,
        }

    porcelain = run(["git", "status", "--porcelain=v1", "-uall"], repo)
    porcelain_lines = [line for line in porcelain.splitlines() if line.strip() and not line.startswith("ERROR:")]
    ahead_behind = re.sub(
        r"\s+",
        " ",
        run(["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"], repo),
    ).strip()

    return {
        "path": str(repo),
        "exists": repo.exists(),
        "isGitRepo": True,
        "branch": run(["git", "branch", "--show-current"], repo),
        "head": run(["git", "rev-parse", "--short", "HEAD"], repo),
        "originMain": run(["git", "rev-parse", "--short", "origin/main"], repo),
        "aheadBehind": ahead_behind,
        "porcelainCount": len(porcelain_lines),
        "clean": len(porcelain_lines) == 0 and ahead_behind == "0 0",
        "recentCommit": run(["git", "log", "--oneline", "-1"], repo),
    }


def cloud_expected_worktree_status() -> dict[str, Any]:
    raw = run(["git", "status", "--porcelain=v1", "-uall"], CLOUD)
    lines = [line for line in raw.splitlines() if line.strip() and not line.startswith("ERROR:")]
    unexpected: list[str] = []

    for line in lines:
        path = line[3:] if len(line) > 3 else line
        is_expected_file = path in EXPECTED_CLOUD_GENERATED_FILES
        is_expected_log = (
            path.startswith("artifacts/logs/week17_layer_mix_v0_observability_evidence_index")
            and path.endswith(".log")
        )
        if not (is_expected_file or is_expected_log):
            unexpected.append(line)

    return {
        "ok": len(unexpected) == 0,
        "porcelainLines": lines,
        "unexpected": unexpected,
    }


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_jsonLoadError": str(exc), "_path": str(path)}


def find_bool(obj: Any, key_names: set[str]) -> bool | None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in key_names and isinstance(value, bool):
                return value
            nested = find_bool(value, key_names)
            if nested is not None:
                return nested
    elif isinstance(obj, list):
        for item in obj:
            nested = find_bool(item, key_names)
            if nested is not None:
                return nested
    return None


def extract_decision(obj: Any) -> str | None:
    if isinstance(obj, dict):
        value = obj.get("decision")
        if isinstance(value, str):
            return value
        for child in obj.values():
            found = extract_decision(child)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = extract_decision(item)
            if found:
                return found
    return None


def decision_text(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, dict):
        chunks = []
        for key, value in obj.items():
            if key.lower() in {"decision", "status", "result"} and isinstance(value, str):
                chunks.append(value)
            elif isinstance(value, (dict, list)):
                chunks.append(decision_text(value))
        return " ".join(x for x in chunks if x)
    if isinstance(obj, list):
        return " ".join(decision_text(x) for x in obj)
    return ""


def bool_from_report(obj: Any, keys: set[str], fallback_patterns: list[str] | None = None) -> bool:
    explicit = find_bool(obj, keys)
    if explicit is not None:
        return explicit
    text = decision_text(obj).lower()
    return any(pattern.lower() in text for pattern in (fallback_patterns or []))


def detect_unsafe_official_claim(reports: dict[str, Any], official_promtool_passed: bool) -> bool:
    if official_promtool_passed:
        return False

    for obj in reports.values():
        explicit = find_bool(
            obj,
            {
                "officialPromtoolPassed",
                "official_promtool_passed",
                "officialPassed",
                "promtoolOfficialPassed",
            },
        )
        if explicit is True:
            return True

        decision = (extract_decision(obj) or "").upper()
        if (
            "PROMTOOL" in decision
            and "OFFICIAL" in decision
            and "PASS" in decision
            and "BLOCKED" not in decision
            and "PARTIAL" not in decision
        ):
            return True

    return False


def metric_family_duplicate_check(text: str) -> dict[str, Any]:
    help_seen: set[str] = set()
    type_seen: set[str] = set()
    duplicates: list[str] = []

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("# HELP "):
            parts = line.split()
            if len(parts) >= 3:
                name = parts[2]
                if name in help_seen:
                    duplicates.append(f"HELP:{name}")
                help_seen.add(name)
        elif line.startswith("# TYPE "):
            parts = line.split()
            if len(parts) >= 3:
                name = parts[2]
                if name in type_seen:
                    duplicates.append(f"TYPE:{name}")
                type_seen.add(name)

    return {
        "helpFamilies": sorted(help_seen),
        "typeFamilies": sorted(type_seen),
        "duplicates": duplicates,
        "ok": len(duplicates) == 0,
    }


def prom_line(name: str, value: int | float, help_text: str, metric_type: str = "gauge") -> str:
    return f"# HELP {name} {help_text}\n# TYPE {name} {metric_type}\n{name} {value}\n"


def main() -> int:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    reports = {name: load_json(path) for name, path in INPUTS.items() if path.suffix == ".json"}

    input_status = {}
    for name, path in INPUTS.items():
        loaded = reports.get(name) if path.suffix == ".json" else None
        input_status[name] = {
            "path": str(path),
            "exists": path.exists(),
            "sizeBytes": path.stat().st_size if path.exists() else 0,
            "jsonLoadable": (
                path.suffix == ".json"
                and path.exists()
                and not (isinstance(loaded, dict) and "_jsonLoadError" in loaded)
            )
            if path.suffix == ".json"
            else None,
            "decision": extract_decision(loaded) if path.suffix == ".json" else None,
        }

    fallback_report = reports.get("cloud_alert_semantic_fallback_report")
    metrics_report = reports.get("cloud_alert_semantic_fallback_metrics_report")
    official_report = reports.get("cloud_official_promtool_report_optional")
    action_gate_report = reports.get("cloud_action_gate_report")

    official_promtool_passed = (
        bool_from_report(
            official_report,
            {"officialPromtoolPassed", "promtoolPassed", "officialPassed", "promtoolOfficialPassed"},
            ["official_promtool_pass", "official promtool pass"],
        )
        if official_report is not None
        else False
    )

    promtool_blocked = bool_from_report(
        metrics_report,
        {"promtoolBlocked"},
        ["promtool_blocked", "promtool blocked", "promtoolblocked"],
    ) or bool_from_report(
        fallback_report,
        {"promtoolBlocked"},
        ["promtool_blocked", "promtool blocked", "promtoolblocked"],
    )

    semantic_fallback_passed = bool_from_report(
        metrics_report,
        {"semanticFallbackPassed"},
        ["local_semantic_pass", "semantic_fallback_pass", "semantic fallback passed"],
    ) or bool_from_report(
        fallback_report,
        {"semanticFallbackPassed"},
        ["local_semantic_pass", "semantic_fallback_pass", "semantic fallback passed"],
    )

    metrics_ready = bool_from_report(
        metrics_report,
        {"metricsReady"},
        ["metrics_ready", "metrics-ready", "metricsready"],
    )

    blocked_claims_preserved = bool_from_report(
        metrics_report,
        {"blockedClaimsPreserved"},
        ["blockedclaimspreserved", "blocked claims preserved"],
    )

    action_gate_ready = action_gate_report is not None and input_status["cloud_action_gate_report"]["exists"]
    mainbase_ready = input_status["mainbase_layer_mix_manifest"]["exists"] and input_status["mainbase_layer_mix_wav"]["exists"]
    java_ready = input_status["java_result_preview_report"]["exists"] and input_status["java_result_preview_payload"]["exists"]
    cloud_preview_ready = input_status["cloud_result_platform_preview"]["exists"]

    all_required_inputs_present = all(
        [
            mainbase_ready,
            java_ready,
            cloud_preview_ready,
            action_gate_ready,
            input_status["cloud_alert_semantic_fallback_report"]["exists"],
            input_status["cloud_alert_semantic_fallback_metrics_report"]["exists"],
            input_status["cloud_alert_semantic_fallback_metrics_prom"]["exists"],
        ]
    )

    unsafe_claim_detected = detect_unsafe_official_claim(reports, official_promtool_passed)
    cloud_expected_status = cloud_expected_worktree_status()

    all_git_clean = all(
        [
            git_summary(MAINBASE)["clean"],
            git_summary(JAVA)["clean"],
            cloud_expected_status["ok"],
        ]
    )

    evidence_index_ready = all(
        [
            all_required_inputs_present,
            all_git_clean,
            metrics_ready,
            blocked_claims_preserved,
            not unsafe_claim_detected,
            official_promtool_passed or (promtool_blocked and semantic_fallback_passed),
        ]
    )

    decision = (
        "PASS_WEEK17_LAYER_MIX_V0_OBSERVABILITY_EVIDENCE_INDEX"
        if evidence_index_ready
        else "BLOCK_WEEK17_LAYER_MIX_V0_OBSERVABILITY_EVIDENCE_INDEX"
    )

    blocked_claims = [
        "Do not claim official promtool pass unless a real promtool test rules report exists and records a pass.",
        "Do not claim live Prometheus scrape.",
        "Do not claim live Grafana import.",
        "Do not claim Alertmanager routing.",
        "Do not claim production alerting.",
        "Do not claim production SLO.",
        "Do not claim semantic audio quality pass or human-review pass.",
        "Do not claim final mix readiness; current mix is placeholder/control evidence.",
    ]

    index = {
        "schemaVersion": "week17.layer_mix_v0.observability_evidence_index.v3",
        "generatedAtUtc": now,
        "decision": decision,
        "evidenceIndexReady": evidence_index_ready,
        "git": {
            "mainbase": git_summary(MAINBASE),
            "java": git_summary(JAVA),
            "cloud": git_summary(CLOUD),
        },
        "inputStatus": input_status,
        "derivedSignals": {
            "allRequiredInputsPresent": all_required_inputs_present,
            "mainbaseLayerMixReady": mainbase_ready,
            "javaResultPreviewReady": java_ready,
            "cloudResultPlatformPreviewReady": cloud_preview_ready,
            "cloudActionGateReady": action_gate_ready,
            "officialPromtoolPassed": official_promtool_passed,
            "promtoolBlocked": promtool_blocked,
            "semanticFallbackPassed": semantic_fallback_passed,
            "metricsReady": metrics_ready,
            "blockedClaimsPreserved": blocked_claims_preserved,
            "unsafeClaimDetected": unsafe_claim_detected,
            "allGitClean": all_git_clean,
            "cloudWorktreeOnlyExpectedOutputs": cloud_expected_status["ok"],
            "cloudUnexpectedChanges": cloud_expected_status["unexpected"],
        },
        "sourceDecisions": {
            name: status.get("decision")
            for name, status in input_status.items()
            if status.get("decision")
        },
        "blockedClaims": blocked_claims,
        "nextWeek17Inputs": {
            "mainbase": "week17_layer_mix_v0_manifest + placeholder_control_mix.wav",
            "java": "week17_layer_mix_v0_result_preview_api_report + payload",
            "cloud": "action_gate + semantic_fallback + metrics_ready + observability_evidence_index",
            "plannedUse": "dashboard-ready aggregation, k6 threshold smoke, SLO boundary explanation",
        },
        "notes": [
            "This index is an offline evidence contract, not a live Prometheus scrape.",
            "promtool official status is separated from local semantic fallback.",
            "Docker/promtool blockage is treated as an environment boundary, not a business failure.",
        ],
    }

    prom = ""
    prom += prom_line("week17_layer_mix_v0_observability_evidence_index_ready", 1 if evidence_index_ready else 0, "Whether the offline Week17 layer mix v0 observability evidence index is ready.")
    prom += prom_line("week17_layer_mix_v0_required_inputs_present", 1 if all_required_inputs_present else 0, "Whether all required upstream evidence files are present.")
    prom += prom_line("week17_layer_mix_v0_official_promtool_passed", 1 if official_promtool_passed else 0, "Whether official promtool rules test has passed.")
    prom += prom_line("week17_layer_mix_v0_promtool_blocked", 1 if promtool_blocked else 0, "Whether official promtool path is blocked locally.")
    prom += prom_line("week17_layer_mix_v0_semantic_fallback_passed", 1 if semantic_fallback_passed else 0, "Whether local semantic fallback passed.")
    prom += prom_line("week17_layer_mix_v0_metrics_ready", 1 if metrics_ready else 0, "Whether metrics-ready artifact is available.")
    prom += prom_line("week17_layer_mix_v0_blocked_claims_preserved", 1 if blocked_claims_preserved else 0, "Whether blocked claims are preserved.")
    prom += prom_line("week17_layer_mix_v0_unsafe_claim_detected", 1 if unsafe_claim_detected else 0, "Whether unsafe official/live/production claim was detected.")
    prom += prom_line("week17_layer_mix_v0_cloud_worktree_only_expected_outputs", 1 if cloud_expected_status["ok"] else 0, "Whether Cloud worktree changes are limited to expected evidence index outputs.")

    prom_check = metric_family_duplicate_check(prom)
    index["prometheusSelfCheck"] = prom_check

    if not prom_check["ok"]:
        index["decision"] = "BLOCK_WEEK17_LAYER_MIX_V0_OBSERVABILITY_EVIDENCE_INDEX_METRICS_DUPLICATE"
        index["evidenceIndexReady"] = False

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_PROM.parent.mkdir(parents=True, exist_ok=True)
    OUT_RUNBOOK.parent.mkdir(parents=True, exist_ok=True)

    OUT_JSON.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_PROM.write_text(prom, encoding="utf-8")

    runbook = f"""# Week17 Layer Mix V0 Observability Evidence Index

Generated at UTC: {now}

## Decision

`{index["decision"]}`

## What this proves

This proves that Mainbase layer mix v0 evidence, Java result preview evidence, Cloud action gate evidence, local semantic fallback evidence, and metrics-ready evidence can be read as one offline observability contract.

## What this does not prove

- It does not prove official promtool pass unless a real promtool test rules report exists and records a pass.
- It does not prove live Prometheus scrape.
- It does not prove live Grafana import.
- It does not prove Alertmanager routing.
- It does not prove production alerting or production SLO.
- It does not prove semantic audio quality pass, human review pass, or final mix readiness.

## Key derived signals

- officialPromtoolPassed: `{official_promtool_passed}`
- promtoolBlocked: `{promtool_blocked}`
- semanticFallbackPassed: `{semantic_fallback_passed}`
- metricsReady: `{metrics_ready}`
- blockedClaimsPreserved: `{blocked_claims_preserved}`
- unsafeClaimDetected: `{unsafe_claim_detected}`
- allRequiredInputsPresent: `{all_required_inputs_present}`
- cloudWorktreeOnlyExpectedOutputs: `{cloud_expected_status["ok"]}`

## Next Week17 usage

Use `loadtest/reports/week17_layer_mix_v0_observability_evidence_index.json` as the single entry point for dashboard-ready aggregation, k6 threshold smoke, and SLO boundary explanation.
"""
    OUT_RUNBOOK.write_text(runbook, encoding="utf-8")

    log_path = LOG_DIR / f"week17_layer_mix_v0_observability_evidence_index_v3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path.write_text(
        "\n".join(
            [
                f"decision={index['decision']}",
                f"evidenceIndexReady={index['evidenceIndexReady']}",
                f"officialPromtoolPassed={official_promtool_passed}",
                f"promtoolBlocked={promtool_blocked}",
                f"semanticFallbackPassed={semantic_fallback_passed}",
                f"metricsReady={metrics_ready}",
                f"blockedClaimsPreserved={blocked_claims_preserved}",
                f"unsafeClaimDetected={unsafe_claim_detected}",
                f"cloudWorktreeOnlyExpectedOutputs={cloud_expected_status['ok']}",
                f"cloudUnexpectedChanges={cloud_expected_status['unexpected']}",
                f"json={OUT_JSON}",
                f"prom={OUT_PROM}",
                f"runbook={OUT_RUNBOOK}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "decision": index["decision"],
                "evidenceIndexReady": index["evidenceIndexReady"],
                "allRequiredInputsPresent": all_required_inputs_present,
                "officialPromtoolPassed": official_promtool_passed,
                "promtoolBlocked": promtool_blocked,
                "semanticFallbackPassed": semantic_fallback_passed,
                "metricsReady": metrics_ready,
                "blockedClaimsPreserved": blocked_claims_preserved,
                "unsafeClaimDetected": unsafe_claim_detected,
                "allGitClean": all_git_clean,
                "cloudWorktreeOnlyExpectedOutputs": cloud_expected_status["ok"],
                "cloudUnexpectedChanges": cloud_expected_status["unexpected"],
                "json": str(OUT_JSON),
                "prom": str(OUT_PROM),
                "runbook": str(OUT_RUNBOOK),
                "log": str(log_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0 if index["evidenceIndexReady"] else 2


if __name__ == "__main__":
    raise SystemExit(main())