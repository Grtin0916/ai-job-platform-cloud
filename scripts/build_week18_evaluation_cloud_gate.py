from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "contracts" / "week18" / "evaluation"
ARTIFACT_DIR = ROOT / "artifacts" / "week18"
LOADTEST_DIR = ROOT / "loadtest" / "reports"
PROM_DIR = ROOT / "observability" / "prometheus"
DASH_DIR = ROOT / "observability" / "grafana" / "dashboards"


def load_json(name: str):
    path = INPUT_DIR / name
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def csv_row_count_hint(report):
    if isinstance(report, dict):
        reports = report.get("reports")
        if isinstance(reports, dict):
            return {
                "audioMetricsRows": reports.get("audio_metrics_csv_rows"),
                "pairwiseRows": reports.get("pairwise_csv_rows"),
                "selectorRows": reports.get("selector_csv_rows"),
            }
    return {}


def main() -> int:
    closure = load_json("w18_eval_closure_20260707.json")
    java_handoff = load_json("week18_evaluation_handoff_report.json")

    counts = closure.get("input_scope", {}) if isinstance(closure, dict) else {}
    row_hints = csv_row_count_hint(closure)

    gate = {
        "gate": "week18_evaluation_cloud_gate",
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "scope": "offline_dashboard_ready_seed",
        "claimBoundary": [
            "This is an offline Cloud aggregation gate.",
            "It does not claim k6 threshold pass.",
            "It does not claim production SLO.",
            "It does not claim live Grafana import."
        ],
        "inputs": sorted(str(p.relative_to(ROOT)) for p in INPUT_DIR.glob("*.json")),
        "mainbase": {
            "expectedCaseCount": counts.get("case_count_expected"),
            "expectedVariantCount": counts.get("variant_count_expected"),
            "expectedCandidateJobs": counts.get("candidate_jobs_expected"),
            "w18AudioFilesWavOrFlac": counts.get("w18_audio_file_count_wav_or_flac"),
            "plotCount": counts.get("plot_count"),
            **row_hints,
        },
        "java": {
            "endpoint": java_handoff.get("endpoint"),
            "controller": java_handoff.get("controller"),
            "test": java_handoff.get("test"),
        },
        "dod": {
            "hasClosure": (INPUT_DIR / "w18_eval_closure_20260707.json").exists(),
            "hasAudioMetrics": (INPUT_DIR / "w18_audio_metrics_eval_20260707.json").exists(),
            "hasPairwise": (INPUT_DIR / "w18_dss_vs_naive_pairwise_report_20260707.json").exists(),
            "hasSelector": (INPUT_DIR / "w18_dss_aware_selector_eval_20260707.json").exists(),
            "hasRepairSeed": (INPUT_DIR / "w18_repair_aware_selector_seed_20260707.json").exists(),
            "hasJavaHandoff": (INPUT_DIR / "week18_evaluation_handoff_report.json").exists(),
        },
    }

    if not all(gate["dod"].values()):
        gate["status"] = "FAIL"

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    LOADTEST_DIR.mkdir(parents=True, exist_ok=True)
    PROM_DIR.mkdir(parents=True, exist_ok=True)
    DASH_DIR.mkdir(parents=True, exist_ok=True)

    gate_json = json.dumps(gate, ensure_ascii=False, indent=2)
    (ARTIFACT_DIR / "w18_evaluation_cloud_gate_20260707.json").write_text(gate_json, encoding="utf-8")
    (LOADTEST_DIR / "week18_evaluation_cloud_gate_20260707.json").write_text(gate_json, encoding="utf-8")

    prom = f"""# HELP week18_evaluation_gate_status Offline W18 evaluation cloud gate status. 1 means pass.
# TYPE week18_evaluation_gate_status gauge
week18_evaluation_gate_status {1 if gate["status"] == "PASS" else 0}
# HELP week18_evaluation_candidate_jobs_expected Expected W18 candidate jobs.
# TYPE week18_evaluation_candidate_jobs_expected gauge
week18_evaluation_candidate_jobs_expected {counts.get("candidate_jobs_expected", 0)}
# HELP week18_evaluation_plot_count Evaluation plot count.
# TYPE week18_evaluation_plot_count gauge
week18_evaluation_plot_count {counts.get("plot_count", 0)}
# HELP week18_evaluation_audio_metric_rows Audio metrics CSV row count.
# TYPE week18_evaluation_audio_metric_rows gauge
week18_evaluation_audio_metric_rows {row_hints.get("audioMetricsRows") or 0}
"""
    (PROM_DIR / "week18_evaluation.prom").write_text(prom, encoding="utf-8")

    dashboard = {
        "title": "Week18 Evaluation Dashboard Ready",
        "tags": ["week18", "evaluation", "offline"],
        "schemaVersion": 39,
        "version": 1,
        "panels": [
            {"type": "stat", "title": "Gate status", "gridPos": {"x": 0, "y": 0, "w": 6, "h": 4}},
            {"type": "stat", "title": "Expected candidate jobs", "gridPos": {"x": 6, "y": 0, "w": 6, "h": 4}},
            {"type": "stat", "title": "Audio metric rows", "gridPos": {"x": 12, "y": 0, "w": 6, "h": 4}},
            {"type": "stat", "title": "Plot count", "gridPos": {"x": 18, "y": 0, "w": 6, "h": 4}},
            {"type": "table", "title": "Claim boundary", "gridPos": {"x": 0, "y": 4, "w": 12, "h": 6}},
            {"type": "table", "title": "Java handoff", "gridPos": {"x": 12, "y": 4, "w": 12, "h": 6}},
        ],
    }
    (DASH_DIR / "week18_evaluation_dashboard.json").write_text(
        json.dumps(dashboard, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(gate, ensure_ascii=False, indent=2))
    return 0 if gate["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
