#!/usr/bin/env python3
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

def run(cmd):
    return subprocess.check_output(cmd, text=True).strip()

def repo_snapshot(repo):
    repo = Path(repo)
    return {
        "repo": str(repo),
        "head": run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"]),
        "originMain": run(["git", "-C", str(repo), "rev-parse", "--short", "origin/main"]),
        "aheadBehind": run(["git", "-C", str(repo), "rev-list", "--left-right", "--count", "HEAD...origin/main"]),
        "porcelainCount": len(run(["git", "-C", str(repo), "status", "--porcelain=v1", "-uall"]).splitlines()),
    }

def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def read_json(path):
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"missing json: {path}")
    return json.loads(path.read_text(encoding="utf-8"))

def metric_line(name, value, labels):
    label_text = ",".join(f'{k}="{str(v).replace(chr(34), chr(92)+chr(34))}"' for k, v in labels.items())
    return f"{name}{{{label_text}}} {value}"

def bool01(v):
    return 1 if v else 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mainbase-root", required=True)
    parser.add_argument("--java-root", required=True)
    parser.add_argument("--cloud-root", default=".")
    parser.add_argument("--out-report", default="loadtest/reports/week15_temporal_alignment_three_repo_signal_review_chain_closure.json")
    parser.add_argument("--out-metrics", default="observability/prometheus/week15_temporal_alignment_three_repo_signal_review_chain_metrics.prom")
    args = parser.parse_args()

    mainbase = Path(args.mainbase_root).resolve()
    java = Path(args.java_root).resolve()
    cloud = Path(args.cloud_root).resolve()

    java_report_path = java / "artifacts/manifests/week15_java_temporal_alignment_review_state_registry_backed_contract_report.json"
    mainbase_gate_path = mainbase / "artifacts/reviews/week15_temporal_alignment_registry_backed_signal_assessment_gate.json"
    cloud_registry_gate_path = cloud / "loadtest/reports/week15_temporal_alignment_review_state_registry_backed_platform_gate.json"
    cloud_signal_index_path = cloud / "loadtest/reports/week15_temporal_alignment_signal_assessment_platform_index.json"
    cloud_signal_gate_path = cloud / "loadtest/reports/week15_temporal_alignment_signal_assessment_platform_gate.json"

    java_report = read_json(java_report_path)
    mainbase_gate = read_json(mainbase_gate_path)
    cloud_registry_gate = read_json(cloud_registry_gate_path)
    cloud_signal_index = read_json(cloud_signal_index_path)
    cloud_signal_gate = read_json(cloud_signal_gate_path)

    snapshots = {
        "mainbase": repo_snapshot(mainbase),
        "java": repo_snapshot(java),
        "cloud": repo_snapshot(cloud),
    }

    signal_summary = cloud_signal_index.get("signalSummary", {})
    cloud_boundary = cloud_signal_index.get("claimBoundary", {})
    delta = mainbase_gate.get("0004SignalDelta", {})

    checks = {
        "mainbase_clean": snapshots["mainbase"]["porcelainCount"] == 0,
        "java_clean": snapshots["java"]["porcelainCount"] == 0,
        "cloud_clean_before_outputs": snapshots["cloud"]["porcelainCount"] == 0,

        "mainbase_head_synced": snapshots["mainbase"]["head"] == snapshots["mainbase"]["originMain"],
        "java_head_synced": snapshots["java"]["head"] == snapshots["java"]["originMain"],
        "cloud_head_synced": snapshots["cloud"]["head"] == snapshots["cloud"]["originMain"],

        "java_registry_contract_pass": java_report.get("decision") == "PASS_REGISTRY_BACKED_REVIEW_STATE_CONTRACT",
        "java_source_registry_backed": java_report.get("sourceType") == "ARTIFACT_REGISTRY_BACKED",
        "java_required_risk_present": java_report.get("requiredRiskCandidatePresent") is True,
        "java_claim_boundary_preserved": java_report.get("claimBoundaryPreserved") is True,
        "java_random_port_not_claimed": java_report.get("springBootRandomPortCompatibilityChecked") is False,

        "mainbase_signal_gate_pass": mainbase_gate.get("decision") == "PASS_WEEK15_REGISTRY_BACKED_SIGNAL_ASSESSMENT_GATE",
        "mainbase_visual_risk_preserved": mainbase_gate.get("visualRisk") == "POSSIBLE_ONSET_PROXY_ANNOTATION_BUG_OR_OVER_SENSITIVE_THRESHOLD",
        "mainbase_0004_burst_shift_supported": delta.get("baselineFirstBurstSec", 0) >= 1.0 and delta.get("remediatedFirstBurstSec", 999) <= 0.10,
        "mainbase_no_human_review_pass": "HUMAN_REVIEW_PASS" in mainbase_gate.get("claimBoundary", ""),

        "cloud_registry_platform_gate_pass": cloud_registry_gate.get("decision") == "PASS_WEEK15_REGISTRY_BACKED_PLATFORM_GATE",
        "cloud_signal_platform_gate_pass": cloud_signal_gate.get("decision") == "PASS_SIGNAL_ASSESSMENT_PLATFORM_GATE",
        "cloud_signal_platform_partial_pass": cloud_signal_index.get("platformDecision") == "PASS_SIGNAL_ASSESSMENT_PARTIAL_PLATFORM_CONSUMPTION",
        "cloud_0004_timing_supported": signal_summary.get("0004TimingSignalSupported") is True,
        "cloud_semantic_not_promoted": cloud_boundary.get("semanticPassClaimed") is False and signal_summary.get("0004SemanticPromoted") is False,
        "cloud_human_review_not_promoted": cloud_boundary.get("humanReviewPassClaimed") is False and signal_summary.get("humanReviewPromoted") is False,
        "cloud_visual_risk_carried": cloud_boundary.get("visualRiskCarried") == "POSSIBLE_ONSET_PROXY_ANNOTATION_BUG_OR_OVER_SENSITIVE_THRESHOLD",
    }

    decision = "PASS_WEEK15_THREE_REPO_SIGNAL_REVIEW_CHAIN_CLOSURE" if all(checks.values()) else "FAIL_WEEK15_THREE_REPO_SIGNAL_REVIEW_CHAIN_CLOSURE"

    report = {
        "schemaVersion": "week15.three-repo.temporal-alignment.signal-review-chain-closure.v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "summary": {
            "chain": "Java registry-backed review-state -> Cloud registry platform gate -> Mainbase signal gate -> Cloud signal platform gate -> three-repo closure",
            "claim": "Signal-level partial support for procedural_v0_0004 timing remediation only. Semantic PASS and HUMAN_REVIEW_PASS are not claimed.",
            "nextAllowedAction": "Record human audition decision only after explicit user-provided semantic/timing/usable judgements.",
        },
        "snapshots": snapshots,
        "artifactHashes": {
            "javaRegistryContractSha256": sha256_file(java_report_path),
            "mainbaseSignalGateSha256": sha256_file(mainbase_gate_path),
            "cloudRegistryGateSha256": sha256_file(cloud_registry_gate_path),
            "cloudSignalPlatformGateSha256": sha256_file(cloud_signal_gate_path),
        },
        "inputs": {
            "javaRegistryContract": str(java_report_path),
            "mainbaseSignalGate": str(mainbase_gate_path),
            "cloudRegistryPlatformGate": str(cloud_registry_gate_path),
            "cloudSignalPlatformIndex": str(cloud_signal_index_path),
            "cloudSignalPlatformGate": str(cloud_signal_gate_path),
        },
        "checks": checks,
        "0004SignalDelta": delta,
        "platformBoundary": {
            "semanticPassClaimed": False,
            "humanReviewPassClaimed": False,
            "randomPortCompatibilityClaimed": False,
            "visualRiskCarried": "POSSIBLE_ONSET_PROXY_ANNOTATION_BUG_OR_OVER_SENSITIVE_THRESHOLD",
        },
    }

    out_report = Path(args.out_report)
    out_metrics = Path(args.out_metrics)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_metrics.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    labels = {
        "week": "week15",
        "chain": "three_repo_signal_review",
        "visual_risk": "POSSIBLE_ONSET_PROXY_ANNOTATION_BUG_OR_OVER_SENSITIVE_THRESHOLD",
    }
    first_shift = round(delta.get("baselineFirstBurstSec", 0) - delta.get("remediatedFirstBurstSec", 0), 6)

    lines = [
        "# HELP week15_three_repo_signal_review_chain_closure_pass Three-repo signal review chain closure pass flag.",
        "# TYPE week15_three_repo_signal_review_chain_closure_pass gauge",
        metric_line("week15_three_repo_signal_review_chain_closure_pass", bool01(decision.startswith("PASS")), labels),
        "# HELP week15_three_repo_signal_review_java_registry_contract_pass Java registry-backed contract pass flag.",
        "# TYPE week15_three_repo_signal_review_java_registry_contract_pass gauge",
        metric_line("week15_three_repo_signal_review_java_registry_contract_pass", bool01(checks["java_registry_contract_pass"]), labels),
        "# HELP week15_three_repo_signal_review_mainbase_signal_gate_pass Mainbase signal gate pass flag.",
        "# TYPE week15_three_repo_signal_review_mainbase_signal_gate_pass gauge",
        metric_line("week15_three_repo_signal_review_mainbase_signal_gate_pass", bool01(checks["mainbase_signal_gate_pass"]), labels),
        "# HELP week15_three_repo_signal_review_cloud_signal_gate_pass Cloud signal platform gate pass flag.",
        "# TYPE week15_three_repo_signal_review_cloud_signal_gate_pass gauge",
        metric_line("week15_three_repo_signal_review_cloud_signal_gate_pass", bool01(checks["cloud_signal_platform_gate_pass"]), labels),
        "# HELP week15_three_repo_signal_review_semantic_pass_claimed Semantic pass claimed flag.",
        "# TYPE week15_three_repo_signal_review_semantic_pass_claimed gauge",
        metric_line("week15_three_repo_signal_review_semantic_pass_claimed", 0, labels),
        "# HELP week15_three_repo_signal_review_human_review_pass_claimed Human review pass claimed flag.",
        "# TYPE week15_three_repo_signal_review_human_review_pass_claimed gauge",
        metric_line("week15_three_repo_signal_review_human_review_pass_claimed", 0, labels),
        "# HELP week15_three_repo_signal_review_0004_first_burst_shift_sec Baseline first burst minus remediated first burst in seconds.",
        "# TYPE week15_three_repo_signal_review_0004_first_burst_shift_sec gauge",
        metric_line("week15_three_repo_signal_review_0004_first_burst_shift_sec", first_shift, labels),
    ]
    out_metrics.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if decision != "PASS_WEEK15_THREE_REPO_SIGNAL_REVIEW_CHAIN_CLOSURE":
        raise SystemExit(5)

if __name__ == "__main__":
    main()
