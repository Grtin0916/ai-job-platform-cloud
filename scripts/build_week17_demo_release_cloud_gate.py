from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(".").resolve()

MAINBASE = Path.home() / "work/audio_engineering_repo_skeleton_v1"
JAVA = Path.home() / "work/media-task-platform-java"

OUT_DIR = ROOT / "artifacts/demo/week17_demo_release_cloud_gate"
INPUTS_DIR = OUT_DIR / "inputs"

GATE_JSON = OUT_DIR / "week17_demo_release_cloud_gate.json"
DASHBOARD_READY_JSON = OUT_DIR / "week17_demo_release_dashboard_ready.json"
LOADTEST_REPORT = ROOT / "loadtest/reports/week17_demo_release_cloud_gate.json"
PROM_SAMPLE = ROOT / "observability/prometheus/week17_demo_release.prom"
PROM_RULES = ROOT / "observability/prometheus/week17_demo_release.rules.yml"
GRAFANA_DASHBOARD = ROOT / "observability/grafana/dashboards/week17_demo_release_dashboard.json"
RUNBOOK = ROOT / "docs/runbooks/week17-demo-release-cloud-gate.md"

MAINBASE_VERIFY = MAINBASE / "reports/week17_demo_release_verify_20260703.json"
MAINBASE_MANIFEST = MAINBASE / "reports/week17_demo_release_manifest_20260703.json"
MAINBASE_CLAIM = MAINBASE / "reports/week17_demo_claim_boundary_card_20260703.json"
MAINBASE_ZIP = MAINBASE / "artifacts/demo/week17_true_aware_demo_release_20260703.zip"

JAVA_HANDOFF = JAVA / "artifacts/manifests/week17_demo_release_handoff/week17_demo_release_handoff_report.json"
JAVA_IT_LOG = JAVA / "artifacts/logs/week17_demo_release_handoff_api_it_20260703.log"


def read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def copy_input(path: Path) -> str:
    INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return ""
    dst = INPUTS_DIR / path.name
    shutil.copy2(path, dst)
    return str(dst.relative_to(ROOT))


def bool01(value: bool) -> int:
    return 1 if value else 0


def analyze_java_it_log(path: Path) -> dict:
    if not path.exists():
        return {
            "logExists": False,
            "summaryDetected": False,
            "failureKeywordDetected": False,
            "buildSuccessDetected": False,
            "testsRunLineDetected": False,
            "verified": False,
        }

    text = path.read_text(encoding="utf-8", errors="replace")
    failure_keyword = bool(re.search(r"\b(BUILD FAILURE|FAILURE|ERROR|Failures:\s*[1-9]|Errors:\s*[1-9])\b", text))
    build_success = "BUILD SUCCESS" in text
    tests_run_line = bool(re.search(r"Tests run:\s*\d+", text))
    zero_failure_line = bool(re.search(r"Failures:\s*0", text)) and bool(re.search(r"Errors:\s*0", text))

    summary_detected = build_success or tests_run_line
    verified = (build_success or zero_failure_line) and not failure_keyword

    return {
        "logExists": True,
        "logPath": str(path),
        "logSizeBytes": path.stat().st_size,
        "summaryDetected": summary_detected,
        "failureKeywordDetected": failure_keyword,
        "buildSuccessDetected": build_success,
        "testsRunLineDetected": tests_run_line,
        "zeroFailureLineDetected": zero_failure_line,
        "verified": verified,
    }


def write_prometheus_sample(gate: dict) -> None:
    PROM_SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    m = gate["metrics"]

    lines = [
        "# HELP week17_demo_release_gate_ready Whether the demo release cloud gate is artifact-ready.",
        "# TYPE week17_demo_release_gate_ready gauge",
        f"week17_demo_release_gate_ready {m['releaseGateReady']}",
        "# HELP week17_demo_release_safe_true_mmaudio_records Number of safe true MMAudio records in the release.",
        "# TYPE week17_demo_release_safe_true_mmaudio_records gauge",
        f"week17_demo_release_safe_true_mmaudio_records {m['safeTrueMmaudioRecordCount']}",
        "# HELP week17_demo_release_zip_valid Whether the release ZIP passed zip validation.",
        "# TYPE week17_demo_release_zip_valid gauge",
        f"week17_demo_release_zip_valid {m['zipValid']}",
        "# HELP week17_demo_release_java_handoff_ready Whether Java handoff artifact is ready.",
        "# TYPE week17_demo_release_java_handoff_ready gauge",
        f"week17_demo_release_java_handoff_ready {m['javaHandoffReady']}",
        "# HELP week17_demo_release_java_random_port_it_verified Whether Java RANDOM_PORT IT pass is explicitly visible in logs.",
        "# TYPE week17_demo_release_java_random_port_it_verified gauge",
        f"week17_demo_release_java_random_port_it_verified {m['javaRandomPortItVerified']}",
        "# HELP week17_demo_release_production_slo_verified Whether production SLO is verified.",
        "# TYPE week17_demo_release_production_slo_verified gauge",
        f"week17_demo_release_production_slo_verified {m['productionSloVerified']}",
        "# HELP week17_demo_release_k6_threshold_pass_verified Whether k6 threshold pass is verified.",
        "# TYPE week17_demo_release_k6_threshold_pass_verified gauge",
        f"week17_demo_release_k6_threshold_pass_verified {m['k6ThresholdPassVerified']}",
        "# HELP week17_demo_release_live_grafana_import_verified Whether live Grafana import is verified.",
        "# TYPE week17_demo_release_live_grafana_import_verified gauge",
        f"week17_demo_release_live_grafana_import_verified {m['liveGrafanaImportVerified']}",
        "",
    ]

    PROM_SAMPLE.write_text("\n".join(lines), encoding="utf-8")


def write_prometheus_rules() -> None:
    PROM_RULES.parent.mkdir(parents=True, exist_ok=True)
    PROM_RULES.write_text(
        """groups:
  - name: week17_demo_release
    rules:
      - alert: Week17DemoReleaseGateNotReady
        expr: week17_demo_release_gate_ready != 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Week17 demo release gate is not ready"
          description: "The artifact-backed demo release gate is not ready. Check Mainbase release, Java handoff, and claim boundary."
      - alert: Week17DemoReleaseOverclaimRisk
        expr: week17_demo_release_production_slo_verified == 1 or week17_demo_release_k6_threshold_pass_verified == 1 or week17_demo_release_live_grafana_import_verified == 1
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Week17 demo release has overclaim risk"
          description: "A production/k6/Grafana flag is true. This should only happen after real tool verification."
""",
        encoding="utf-8",
    )


def write_dashboard_json(gate: dict) -> None:
    GRAFANA_DASHBOARD.parent.mkdir(parents=True, exist_ok=True)
    dashboard = {
        "title": "Week17 Demo Release Candidate",
        "tags": ["week17", "true-aware", "demo-release"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "30s",
        "panels": [
            {"id": 1, "type": "stat", "title": "Release Gate Ready", "targets": [{"expr": "week17_demo_release_gate_ready"}]},
            {"id": 2, "type": "stat", "title": "Safe True MMAudio Records", "targets": [{"expr": "week17_demo_release_safe_true_mmaudio_records"}]},
            {"id": 3, "type": "stat", "title": "ZIP Valid", "targets": [{"expr": "week17_demo_release_zip_valid"}]},
            {"id": 4, "type": "stat", "title": "Java Handoff Ready", "targets": [{"expr": "week17_demo_release_java_handoff_ready"}]},
            {"id": 5, "type": "stat", "title": "Java RANDOM_PORT IT Verified", "targets": [{"expr": "week17_demo_release_java_random_port_it_verified"}]},
            {"id": 6, "type": "stat", "title": "k6 Threshold Pass Verified", "targets": [{"expr": "week17_demo_release_k6_threshold_pass_verified"}]},
        ],
    }
    GRAFANA_DASHBOARD.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")

    dashboard_ready = {
        "dashboardReady": True,
        "liveGrafanaImportVerified": False,
        "dashboardPath": str(GRAFANA_DASHBOARD.relative_to(ROOT)),
        "panelCount": len(dashboard["panels"]),
        "dataSourceExpectation": "Prometheus-compatible metrics sample generated locally; no live Grafana import claimed.",
        "gateSummary": gate["summary"],
    }
    DASHBOARD_READY_JSON.write_text(json.dumps(dashboard_ready, ensure_ascii=False, indent=2), encoding="utf-8")


def write_runbook(gate: dict) -> None:
    RUNBOOK.parent.mkdir(parents=True, exist_ok=True)
    RUNBOOK.write_text(
        f"""# Week17 Demo Release Cloud Gate Runbook

## Purpose

Aggregate Mainbase demo release and Java handoff into a Cloud-side release gate.

## Current decision

- releaseGateReady: `{gate["cloudGate"]["releaseGateReady"]}`
- dashboardReady: `{gate["cloudGate"]["dashboardReady"]}`
- prometheusSampleReady: `{gate["cloudGate"]["prometheusSampleReady"]}`
- alertRulesDraftReady: `{gate["cloudGate"]["alertRulesDraftReady"]}`

## Claim boundary

The gate may claim:

- Mainbase release ZIP is valid.
- Release contains `index.html`.
- Release contains at least one WAV fallback.
- Java handoff artifact is available.
- Cloud has dashboard-ready and Prometheus-sample artifacts.

The gate must not claim:

- production SLO verification
- k6 threshold pass
- live Grafana import
- live service availability

## Known limitation

Java RANDOM_PORT IT explicit summary detection:

`{gate["java"]["randomPortIt"]}`

If the Maven log is quiet because of `-q`, the gate does not upgrade it to verified automatically. This is intentional: evidence is separated from inference.
""",
        encoding="utf-8",
    )


def main() -> int:
    for p in [
        OUT_DIR,
        INPUTS_DIR,
        LOADTEST_REPORT.parent,
        PROM_SAMPLE.parent,
        PROM_RULES.parent,
        GRAFANA_DASHBOARD.parent,
        RUNBOOK.parent,
    ]:
        p.mkdir(parents=True, exist_ok=True)

    mainbase_verify = read_json(MAINBASE_VERIFY)
    mainbase_manifest = read_json(MAINBASE_MANIFEST)
    mainbase_claim = read_json(MAINBASE_CLAIM)
    java_handoff = read_json(JAVA_HANDOFF)
    java_it = analyze_java_it_log(JAVA_IT_LOG)

    copied_inputs = {
        "mainbaseVerify": copy_input(MAINBASE_VERIFY),
        "mainbaseManifest": copy_input(MAINBASE_MANIFEST),
        "mainbaseClaim": copy_input(MAINBASE_CLAIM),
        "javaHandoff": copy_input(JAVA_HANDOFF),
        "javaItLog": copy_input(JAVA_IT_LOG),
    }

    checks = mainbase_verify.get("checks", {})
    claim_boundary = {
        "safeTrueMmaudioRecordCount": mainbase_claim.get("safeTrueMmaudioRecordCount", 0),
        "trueMmaudioBatchSuccess": bool(mainbase_claim.get("trueMmaudioBatchSuccess")),
        "fullCandidateRankingAvailable": bool(mainbase_claim.get("fullCandidateRankingAvailable")),
        "productionSloVerified": bool(mainbase_claim.get("productionSloVerified")),
        "k6ThresholdPassVerified": bool(mainbase_claim.get("k6ThresholdPassVerified")),
        "liveGrafanaImportVerified": bool(mainbase_claim.get("liveGrafanaImportVerified")),
    }
    boundary_preserved = all(
        claim_boundary[k] is False
        for k in [
            "trueMmaudioBatchSuccess",
            "fullCandidateRankingAvailable",
            "productionSloVerified",
            "k6ThresholdPassVerified",
            "liveGrafanaImportVerified",
        ]
    )

    mainbase_ready = all(
        [
            mainbase_verify.get("decision") == "PASS",
            checks.get("zip_valid") is True,
            checks.get("zip_contains_index") is True,
            checks.get("zip_contains_wav") is True,
            checks.get("safe_true_mmaudio_record_count", 0) >= 1,
            MAINBASE_ZIP.exists(),
        ]
    )

    java_handoff_ready = bool(java_handoff.get("releaseHandoffReady"))

    release_gate_ready = all(
        [
            mainbase_ready,
            java_handoff_ready,
            boundary_preserved,
            claim_boundary["safeTrueMmaudioRecordCount"] >= 1,
        ]
    )

    gate = {
        "contractVersion": "week17-demo-release-cloud-gate-v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "decision": "PASS" if release_gate_ready else "FAIL",
            "releaseGateReady": release_gate_ready,
            "interpretation": "Artifact-backed demo release gate. Not a production SLO, k6 threshold, or live Grafana import claim.",
        },
        "mainbase": {
            "releaseReady": mainbase_ready,
            "verifyDecision": mainbase_verify.get("decision"),
            "releaseId": mainbase_manifest.get("release_id"),
            "releaseZip": str(MAINBASE_ZIP),
            "releaseZipExists": MAINBASE_ZIP.exists(),
            "releaseZipSizeBytes": MAINBASE_ZIP.stat().st_size if MAINBASE_ZIP.exists() else 0,
            "zipValid": checks.get("zip_valid"),
            "zipContainsIndex": checks.get("zip_contains_index"),
            "zipContainsWav": checks.get("zip_contains_wav"),
            "wavCount": mainbase_manifest.get("wav_count"),
            "trueMmaudioWavCount": mainbase_manifest.get("true_mmaudio_wav_count"),
        },
        "java": {
            "handoffReady": java_handoff_ready,
            "contractVersion": java_handoff.get("contractVersion"),
            "endpoint": java_handoff.get("javaApi", {}).get("endpoint"),
            "randomPortIt": java_it,
        },
        "cloudGate": {
            "releaseGateReady": release_gate_ready,
            "dashboardReady": True,
            "prometheusSampleReady": True,
            "alertRulesDraftReady": True,
            "runbookReady": True,
            "productionSloVerified": False,
            "k6ThresholdPassVerified": False,
            "liveGrafanaImportVerified": False,
        },
        "claimBoundary": {
            **claim_boundary,
            "boundaryPreserved": boundary_preserved,
            "allowedClaims": mainbase_claim.get("allowed_claims", []),
            "blockedClaims": mainbase_claim.get("blocked_claims", []),
        },
        "inputs": copied_inputs,
        "metrics": {
            "releaseGateReady": bool01(release_gate_ready),
            "safeTrueMmaudioRecordCount": int(claim_boundary["safeTrueMmaudioRecordCount"]),
            "zipValid": bool01(checks.get("zip_valid") is True),
            "javaHandoffReady": bool01(java_handoff_ready),
            "javaRandomPortItVerified": bool01(java_it["verified"]),
            "productionSloVerified": 0,
            "k6ThresholdPassVerified": 0,
            "liveGrafanaImportVerified": 0,
        },
    }

    GATE_JSON.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    LOADTEST_REPORT.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    write_prometheus_sample(gate)
    write_prometheus_rules()
    write_dashboard_json(gate)
    write_runbook(gate)

    print(json.dumps(
        {
            "decision": gate["summary"]["decision"],
            "releaseGateReady": release_gate_ready,
            "mainbaseReady": mainbase_ready,
            "javaHandoffReady": java_handoff_ready,
            "javaRandomPortItVerified": java_it["verified"],
            "javaRandomPortItSummaryDetected": java_it["summaryDetected"],
            "dashboardReady": True,
            "prometheusSampleReady": True,
            "k6ThresholdPassVerified": False,
            "liveGrafanaImportVerified": False,
            "gateJson": str(GATE_JSON.relative_to(ROOT)),
            "prometheusSample": str(PROM_SAMPLE.relative_to(ROOT)),
            "dashboardReadyJson": str(DASHBOARD_READY_JSON.relative_to(ROOT)),
            "runbook": str(RUNBOOK.relative_to(ROOT)),
        },
        ensure_ascii=False,
        indent=2,
    ))

    return 0 if release_gate_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())