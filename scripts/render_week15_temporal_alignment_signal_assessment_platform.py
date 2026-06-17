#!/usr/bin/env python3
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def git_head(repo_path):
    return subprocess.check_output(
        ["git", "-C", str(repo_path), "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()

def git_origin_main(repo_path):
    return subprocess.check_output(
        ["git", "-C", str(repo_path), "rev-parse", "--short", "origin/main"],
        text=True,
    ).strip()

def metric_line(name, value, labels):
    label_text = ",".join(f'{k}="{str(v).replace(chr(34), chr(92)+chr(34))}"' for k, v in labels.items())
    return f"{name}{{{label_text}}} {value}"

def bool01(v):
    return 1 if v else 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mainbase-gate", required=True)
    parser.add_argument("--out-index", default="loadtest/reports/week15_temporal_alignment_signal_assessment_platform_index.json")
    parser.add_argument("--out-metrics", default="observability/prometheus/week15_temporal_alignment_signal_assessment_metrics.prom")
    parser.add_argument("--out-gate", default="loadtest/reports/week15_temporal_alignment_signal_assessment_platform_gate.json")
    args = parser.parse_args()

    gate_path = Path(args.mainbase_gate)
    if not gate_path.exists():
        raise SystemExit(f"missing mainbase gate: {gate_path}")

    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    mainbase_repo_root = gate_path.resolve().parents[2]
    cloud_repo_root = Path.cwd().resolve()

    delta = gate.get("0004SignalDelta", {})
    checks = gate.get("checks", {})
    all_gate_checks_true = all(checks.values()) if checks else False

    signal_partial_ok = (
        gate.get("decision") == "PASS_WEEK15_REGISTRY_BACKED_SIGNAL_ASSESSMENT_GATE"
        and all_gate_checks_true
        and gate.get("visualRisk") == "POSSIBLE_ONSET_PROXY_ANNOTATION_BUG_OR_OVER_SENSITIVE_THRESHOLD"
        and delta.get("baselineFirstBurstSec", 0) >= 1.0
        and delta.get("remediatedFirstBurstSec", 999) <= 0.10
        and delta.get("baselineBurstCount") == 2
        and delta.get("remediatedBurstCount") == 2
    )

    platform_decision = (
        "PASS_SIGNAL_ASSESSMENT_PARTIAL_PLATFORM_CONSUMPTION"
        if signal_partial_ok
        else "FAIL_SIGNAL_ASSESSMENT_PARTIAL_PLATFORM_CONSUMPTION"
    )

    index = {
        "schemaVersion": "week15.cloud.temporal-alignment.signal-assessment-platform-index.v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "platformDecision": platform_decision,
        "mainbaseSignalGate": {
            "path": str(gate_path),
            "decision": gate.get("decision"),
            "visualRisk": gate.get("visualRisk"),
            "claimBoundary": gate.get("claimBoundary"),
            "nextAllowedAction": gate.get("nextAllowedAction"),
        },
        "sourceSnapshot": {
            "mainbaseRepoRoot": str(mainbase_repo_root),
            "mainbaseHeadAtConsumption": git_head(mainbase_repo_root),
            "mainbaseOriginMainAtConsumption": git_origin_main(mainbase_repo_root),
            "mainbaseGateSha256": sha256_file(gate_path),
            "cloudInputHead": git_head(cloud_repo_root),
        },
        "signalSummary": {
            "0004TimingSignalSupported": checks.get("0004_timing_supported") is True,
            "0004SignalSupported": checks.get("0004_signal_supported") is True,
            "0004SemanticPromoted": False,
            "humanReviewPromoted": False,
            "baselineFirstBurstSec": delta.get("baselineFirstBurstSec"),
            "remediatedFirstBurstSec": delta.get("remediatedFirstBurstSec"),
            "baselineBurstCount": delta.get("baselineBurstCount"),
            "remediatedBurstCount": delta.get("remediatedBurstCount"),
            "baselinePeakAbs": delta.get("baselinePeakAbs"),
            "remediatedPeakAbs": delta.get("remediatedPeakAbs"),
        },
        "claimBoundary": {
            "platformClaim": "Cloud consumed Mainbase signal-only partial assessment. It does not claim semantic PASS or HUMAN_REVIEW_PASS.",
            "semanticPassClaimed": False,
            "humanReviewPassClaimed": False,
            "visualRiskCarried": gate.get("visualRisk"),
        },
        "artifactLinks": {
            "mainbaseSignalGate": str(gate_path),
            "cloudPlatformIndex": args.out_index,
            "cloudMetrics": args.out_metrics,
            "cloudGate": args.out_gate,
        },
    }

    out_index = Path(args.out_index)
    out_metrics = Path(args.out_metrics)
    out_gate = Path(args.out_gate)
    out_index.parent.mkdir(parents=True, exist_ok=True)
    out_metrics.parent.mkdir(parents=True, exist_ok=True)
    out_gate.parent.mkdir(parents=True, exist_ok=True)

    out_index.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    labels = {
        "week": "week15",
        "source": "mainbase_signal_assessment",
        "visual_risk": gate.get("visualRisk", "UNKNOWN"),
    }

    lines = [
        "# HELP week15_temporal_alignment_signal_assessment_platform_pass Mainbase signal assessment platform consumption pass flag.",
        "# TYPE week15_temporal_alignment_signal_assessment_platform_pass gauge",
        metric_line("week15_temporal_alignment_signal_assessment_platform_pass", bool01(signal_partial_ok), labels),
        "# HELP week15_temporal_alignment_signal_assessment_0004_timing_supported 0004 timing signal supported flag.",
        "# TYPE week15_temporal_alignment_signal_assessment_0004_timing_supported gauge",
        metric_line("week15_temporal_alignment_signal_assessment_0004_timing_supported", bool01(index["signalSummary"]["0004TimingSignalSupported"]), labels),
        "# HELP week15_temporal_alignment_signal_assessment_semantic_pass_claimed Semantic pass claimed flag.",
        "# TYPE week15_temporal_alignment_signal_assessment_semantic_pass_claimed gauge",
        metric_line("week15_temporal_alignment_signal_assessment_semantic_pass_claimed", 0, labels),
        "# HELP week15_temporal_alignment_signal_assessment_human_review_pass_claimed Human review pass claimed flag.",
        "# TYPE week15_temporal_alignment_signal_assessment_human_review_pass_claimed gauge",
        metric_line("week15_temporal_alignment_signal_assessment_human_review_pass_claimed", 0, labels),
        "# HELP week15_temporal_alignment_signal_assessment_visual_risk_carried Visual risk carried flag.",
        "# TYPE week15_temporal_alignment_signal_assessment_visual_risk_carried gauge",
        metric_line("week15_temporal_alignment_signal_assessment_visual_risk_carried", bool01(gate.get("visualRisk") == "POSSIBLE_ONSET_PROXY_ANNOTATION_BUG_OR_OVER_SENSITIVE_THRESHOLD"), labels),
        "# HELP week15_temporal_alignment_signal_assessment_0004_first_burst_shift_sec Baseline first burst minus remediated first burst in seconds.",
        "# TYPE week15_temporal_alignment_signal_assessment_0004_first_burst_shift_sec gauge",
        metric_line(
            "week15_temporal_alignment_signal_assessment_0004_first_burst_shift_sec",
            round(delta.get("baselineFirstBurstSec", 0) - delta.get("remediatedFirstBurstSec", 0), 6),
            labels,
        ),
    ]
    out_metrics.write_text("\n".join(lines) + "\n", encoding="utf-8")

    gate_report = {
        "schemaVersion": "week15.cloud.temporal-alignment.signal-assessment-platform-gate.v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "decision": "PASS_SIGNAL_ASSESSMENT_PLATFORM_GATE" if signal_partial_ok else "FAIL_SIGNAL_ASSESSMENT_PLATFORM_GATE",
        "indexPath": str(out_index),
        "metricsPath": str(out_metrics),
        "checks": {
            "platform_decision_pass": platform_decision == "PASS_SIGNAL_ASSESSMENT_PARTIAL_PLATFORM_CONSUMPTION",
            "mainbase_gate_pass": gate.get("decision") == "PASS_WEEK15_REGISTRY_BACKED_SIGNAL_ASSESSMENT_GATE",
            "all_mainbase_checks_true": all_gate_checks_true,
            "0004_timing_signal_supported": index["signalSummary"]["0004TimingSignalSupported"] is True,
            "semantic_not_promoted": index["claimBoundary"]["semanticPassClaimed"] is False,
            "human_review_not_promoted": index["claimBoundary"]["humanReviewPassClaimed"] is False,
            "visual_risk_carried": index["claimBoundary"]["visualRiskCarried"] == "POSSIBLE_ONSET_PROXY_ANNOTATION_BUG_OR_OVER_SENSITIVE_THRESHOLD",
            "mainbase_head_recorded": bool(index["sourceSnapshot"]["mainbaseHeadAtConsumption"]),
            "mainbase_gate_sha_recorded": len(index["sourceSnapshot"]["mainbaseGateSha256"]) == 64,
        },
    }
    out_gate.write_text(json.dumps(gate_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(index, ensure_ascii=False, indent=2))
    print(json.dumps(gate_report, ensure_ascii=False, indent=2))

    if gate_report["decision"] != "PASS_SIGNAL_ASSESSMENT_PLATFORM_GATE":
        raise SystemExit(5)

if __name__ == "__main__":
    main()
