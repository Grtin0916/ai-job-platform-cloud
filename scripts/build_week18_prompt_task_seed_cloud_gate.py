from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(".").resolve()
MAINBASE = Path.home() / "work/audio_engineering_repo_skeleton_v1"
JAVA = Path.home() / "work/media-task-platform-java"

OUT_DIR = ROOT / "artifacts/demo/week18_prompt_task_seed_cloud_gate"
INPUTS_DIR = OUT_DIR / "inputs"

GATE_JSON = OUT_DIR / "week18_prompt_task_seed_cloud_gate.json"
DASHBOARD_READY_JSON = OUT_DIR / "week18_prompt_task_seed_dashboard_ready.json"
LOADTEST_REPORT = ROOT / "loadtest/reports/week18_prompt_task_seed_cloud_gate.json"
PROM_SAMPLE = ROOT / "observability/prometheus/week18_prompt_task_seed.prom"
PROM_RULES = ROOT / "observability/prometheus/week18_prompt_task_seed.rules.yml"
GRAFANA_DASHBOARD = ROOT / "observability/grafana/dashboards/week18_prompt_task_seed_dashboard.json"
RUNBOOK = ROOT / "docs/runbooks/week18-prompt-task-seed-cloud-gate.md"

MAINBASE_VERIFY = MAINBASE / "reports/week18_prompt_task_verify_20260703.json"
MAINBASE_TASKS = MAINBASE / "reports/week18_prompt_tasks_20260703.jsonl"
MAINBASE_SUMMARY = MAINBASE / "reports/week18_prompt_task_summary_20260703.csv"
MAINBASE_SEED = MAINBASE / "reports/week18_seed_from_week17_demo_release_20260703.json"
JAVA_REPORT = JAVA / "artifacts/manifests/week18_prompt_task_seed/week18_prompt_task_seed_api_report.json"
JAVA_IT_LOG = JAVA / "artifacts/logs/week18_prompt_task_seed_api_it_20260703.log"


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


def bool01(v: bool) -> int:
    return 1 if v else 0


def analyze_java_it_log(path: Path) -> dict:
    if not path.exists():
        return {
            "logExists": False,
            "summaryDetected": False,
            "failureKeywordDetected": False,
            "buildSuccessDetected": False,
            "testsRunLineDetected": False,
            "zeroFailureLineDetected": False,
            "verified": False,
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    failure = bool(re.search(r"\b(BUILD FAILURE|FAILURE|ERROR|Failures:\s*[1-9]|Errors:\s*[1-9])\b", text))
    build_success = "BUILD SUCCESS" in text
    tests_run = bool(re.search(r"Tests run:\s*\d+", text))
    zero_failure = bool(re.search(r"Failures:\s*0", text)) and bool(re.search(r"Errors:\s*0", text))
    verified = (build_success or zero_failure) and not failure
    return {
        "logExists": True,
        "logPath": str(path),
        "logSizeBytes": path.stat().st_size,
        "summaryDetected": build_success or tests_run,
        "failureKeywordDetected": failure,
        "buildSuccessDetected": build_success,
        "testsRunLineDetected": tests_run,
        "zeroFailureLineDetected": zero_failure,
        "verified": verified,
    }


def write_prom(gate: dict) -> None:
    m = gate["metrics"]
    PROM_SAMPLE.write_text("\n".join([
        "# HELP week18_prompt_task_seed_gate_ready Whether W18 prompt task seed cloud gate is ready.",
        "# TYPE week18_prompt_task_seed_gate_ready gauge",
        f"week18_prompt_task_seed_gate_ready {m['gateReady']}",
        "# HELP week18_prompt_task_seed_task_count Number of prompt tasks.",
        "# TYPE week18_prompt_task_seed_task_count gauge",
        f"week18_prompt_task_seed_task_count {m['taskCount']}",
        "# HELP week18_prompt_task_seed_case_count Number of W18 seed cases.",
        "# TYPE week18_prompt_task_seed_case_count gauge",
        f"week18_prompt_task_seed_case_count {m['caseCount']}",
        "# HELP week18_prompt_task_seed_naive_count Number of naive prompt tasks.",
        "# TYPE week18_prompt_task_seed_naive_count gauge",
        f"week18_prompt_task_seed_naive_count {m['naiveCount']}",
        "# HELP week18_prompt_task_seed_dss_count Number of DSS prompt tasks.",
        "# TYPE week18_prompt_task_seed_dss_count gauge",
        f"week18_prompt_task_seed_dss_count {m['dssCount']}",
        "# HELP week18_prompt_task_seed_java_it_verified Whether Java RANDOM_PORT IT is explicitly verified.",
        "# TYPE week18_prompt_task_seed_java_it_verified gauge",
        f"week18_prompt_task_seed_java_it_verified {m['javaItVerified']}",
        "# HELP week18_prompt_task_seed_boundary_preserved Whether claim boundary is preserved.",
        "# TYPE week18_prompt_task_seed_boundary_preserved gauge",
        f"week18_prompt_task_seed_boundary_preserved {m['boundaryPreserved']}",
        "# HELP week18_prompt_task_seed_k6_threshold_pass_verified Whether k6 threshold pass is verified.",
        "# TYPE week18_prompt_task_seed_k6_threshold_pass_verified gauge",
        "week18_prompt_task_seed_k6_threshold_pass_verified 0",
        "# HELP week18_prompt_task_seed_live_grafana_import_verified Whether live Grafana import is verified.",
        "# TYPE week18_prompt_task_seed_live_grafana_import_verified gauge",
        "week18_prompt_task_seed_live_grafana_import_verified 0",
        "",
    ]), encoding="utf-8")


def write_rules() -> None:
    PROM_RULES.write_text("""groups:
  - name: week18_prompt_task_seed
    rules:
      - alert: Week18PromptTaskSeedGateNotReady
        expr: week18_prompt_task_seed_gate_ready != 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "W18 prompt task seed gate is not ready"
          description: "Check Mainbase prompt task queue, Java seed API report, and claim boundary."
      - alert: Week18PromptTaskSeedOverclaimRisk
        expr: week18_prompt_task_seed_k6_threshold_pass_verified == 1 or week18_prompt_task_seed_live_grafana_import_verified == 1
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "W18 prompt task seed has overclaim risk"
          description: "k6 or live Grafana flag is true without a verified run."
""", encoding="utf-8")


def write_dashboard(gate: dict) -> None:
    dashboard = {
        "title": "Week18 Prompt Task Seed",
        "tags": ["week18", "dss", "prompt-seed"],
        "schemaVersion": 39,
        "version": 1,
        "refresh": "30s",
        "panels": [
            {"id": 1, "type": "stat", "title": "Gate Ready", "targets": [{"expr": "week18_prompt_task_seed_gate_ready"}]},
            {"id": 2, "type": "stat", "title": "Task Count", "targets": [{"expr": "week18_prompt_task_seed_task_count"}]},
            {"id": 3, "type": "stat", "title": "Case Count", "targets": [{"expr": "week18_prompt_task_seed_case_count"}]},
            {"id": 4, "type": "stat", "title": "Naive Prompt Count", "targets": [{"expr": "week18_prompt_task_seed_naive_count"}]},
            {"id": 5, "type": "stat", "title": "DSS Prompt Count", "targets": [{"expr": "week18_prompt_task_seed_dss_count"}]},
            {"id": 6, "type": "stat", "title": "Java IT Verified", "targets": [{"expr": "week18_prompt_task_seed_java_it_verified"}]},
        ],
    }
    GRAFANA_DASHBOARD.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")
    DASHBOARD_READY_JSON.write_text(json.dumps({
        "dashboardReady": True,
        "liveGrafanaImportVerified": False,
        "dashboardPath": str(GRAFANA_DASHBOARD.relative_to(ROOT)),
        "panelCount": len(dashboard["panels"]),
        "gateSummary": gate["summary"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def write_runbook(gate: dict) -> None:
    RUNBOOK.write_text(f"""# Week18 Prompt Task Seed Cloud Gate Runbook

## Purpose

Aggregate Mainbase W18 prompt task queue and Java prompt seed API into a Cloud-side seed gate.

## Current decision

- decision: `{gate["summary"]["decision"]}`
- gateReady: `{gate["summary"]["gateReady"]}`
- taskCount: `{gate["mainbase"]["taskCount"]}`
- caseCount: `{gate["mainbase"]["caseCount"]}`
- javaItVerified: `{gate["java"]["randomPortIt"]["verified"]}`

## What this proves

- Six cases have naive and DSS prompt variants.
- W18 has a machine-readable prompt task queue.
- Java exposes the seed as an artifact-backed API.
- Cloud has metrics, dashboard-ready, alert rules, and runbook artifacts.

## What this does not prove

- No model ablation has run yet.
- No k6 threshold pass is claimed.
- No live Grafana import is claimed.
- No production SLO is claimed.
""", encoding="utf-8")


def main() -> int:
    for p in [OUT_DIR, INPUTS_DIR, LOADTEST_REPORT.parent, PROM_SAMPLE.parent, PROM_RULES.parent, GRAFANA_DASHBOARD.parent, RUNBOOK.parent]:
        p.mkdir(parents=True, exist_ok=True)

    mainbase_verify = read_json(MAINBASE_VERIFY)
    java_report = read_json(JAVA_REPORT)
    java_it = analyze_java_it_log(JAVA_IT_LOG)

    prompt_counts = mainbase_verify.get("prompt_type_counts", {})
    boundary = mainbase_verify.get("claim_boundary", {})
    boundary_preserved = all(
        boundary.get(k) is False
        for k in [
            "trueMmaudioBatchSuccess",
            "fullCandidateRankingAvailable",
            "productionSloVerified",
            "k6ThresholdPassVerified",
            "liveGrafanaImportVerified",
        ]
    )

    mainbase_ready = all([
        mainbase_verify.get("decision") == "PASS",
        mainbase_verify.get("task_count") == 12,
        mainbase_verify.get("case_count") == 6,
        prompt_counts.get("naive") == 6,
        prompt_counts.get("dss") == 6,
        mainbase_verify.get("all_cases_have_naive_and_dss") is True,
        MAINBASE_TASKS.exists(),
    ])
    java_ready = bool(java_report.get("promptTaskSeedReady"))
    gate_ready = mainbase_ready and java_ready and java_it["verified"] and boundary_preserved

    gate = {
        "contractVersion": "week18-prompt-task-seed-cloud-gate-v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "decision": "PASS" if gate_ready else "FAIL",
            "gateReady": gate_ready,
            "interpretation": "Cloud-side seed gate for W18 DSS-vs-naive prompt ablation. Not a model-quality or production-SLO claim.",
        },
        "mainbase": {
            "ready": mainbase_ready,
            "taskCount": mainbase_verify.get("task_count"),
            "caseCount": mainbase_verify.get("case_count"),
            "promptTypeCounts": prompt_counts,
            "trueAnchorTaskCount": mainbase_verify.get("true_anchor_task_count"),
            "repairTargetCount": mainbase_verify.get("repair_target_count"),
            "allCasesHaveNaiveAndDss": mainbase_verify.get("all_cases_have_naive_and_dss"),
        },
        "java": {
            "ready": java_ready,
            "endpoint": java_report.get("javaApi", {}).get("endpoint"),
            "randomPortIt": java_it,
        },
        "cloudGate": {
            "dashboardReady": True,
            "prometheusSampleReady": True,
            "alertRulesDraftReady": True,
            "runbookReady": True,
            "k6ThresholdPassVerified": False,
            "liveGrafanaImportVerified": False,
            "productionSloVerified": False,
        },
        "claimBoundary": {
            **boundary,
            "boundaryPreserved": boundary_preserved,
        },
        "inputs": {
            "mainbaseVerify": copy_input(MAINBASE_VERIFY),
            "mainbaseTasks": copy_input(MAINBASE_TASKS),
            "mainbaseSummary": copy_input(MAINBASE_SUMMARY),
            "mainbaseSeed": copy_input(MAINBASE_SEED),
            "javaReport": copy_input(JAVA_REPORT),
            "javaItLog": copy_input(JAVA_IT_LOG),
        },
        "metrics": {
            "gateReady": bool01(gate_ready),
            "taskCount": int(mainbase_verify.get("task_count", 0)),
            "caseCount": int(mainbase_verify.get("case_count", 0)),
            "naiveCount": int(prompt_counts.get("naive", 0)),
            "dssCount": int(prompt_counts.get("dss", 0)),
            "javaItVerified": bool01(java_it["verified"]),
            "boundaryPreserved": bool01(boundary_preserved),
        },
    }

    GATE_JSON.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    LOADTEST_REPORT.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    write_prom(gate)
    write_rules()
    write_dashboard(gate)
    write_runbook(gate)

    print(json.dumps({
        "decision": gate["summary"]["decision"],
        "gateReady": gate_ready,
        "mainbaseReady": mainbase_ready,
        "javaReady": java_ready,
        "javaItVerified": java_it["verified"],
        "taskCount": gate["mainbase"]["taskCount"],
        "caseCount": gate["mainbase"]["caseCount"],
        "promptTypeCounts": gate["mainbase"]["promptTypeCounts"],
        "boundaryPreserved": boundary_preserved,
        "k6ThresholdPassVerified": False,
        "liveGrafanaImportVerified": False,
        "gateJson": str(GATE_JSON.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))

    return 0 if gate_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
