#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOTS = {
    "mainbase": Path.home() / "work/grt_work/audio_engineering_repo_skeleton_v1",
    "java": Path.home() / "work/grt_work/media-task-platform-java",
    "cloud": Path.home() / "work/grt_work/ai-job-platform-cloud",
}

CLOUD_SELF_ARTIFACT_PREFIXES = [
    "scripts/build_week15_temporal_alignment_three_repo_closure_index.py",
    "loadtest/reports/week15_temporal_alignment_eval_v1_three_repo_closure_index.json",
    "observability/prometheus/week15_temporal_alignment_eval_v1_three_repo_closure_metrics.prom",
    "artifacts/logs/week15_temporal_alignment_eval_v1_three_repo_closure_",
]

ARTIFACTS = {
    "mainbaseExplicitRiskContract": ROOTS["mainbase"] / "artifacts/evals/week15_temporal_alignment_explicit_risk_contract.json",
    "javaExplicitRiskConsumerReport": ROOTS["java"] / "artifacts/manifests/week15_java_explicit_risk_contract_consumer_report.json",
    "cloudJavaContractPlatformGate": ROOTS["cloud"] / "loadtest/reports/week15_temporal_alignment_java_explicit_risk_contract_platform_gate.json",
    "cloudJavaContractDashboardReady": ROOTS["cloud"] / "loadtest/reports/week15_temporal_alignment_eval_v1_java_contract_dashboard_ready.json",
}

OUT = ROOTS["cloud"] / "loadtest/reports/week15_temporal_alignment_eval_v1_three_repo_closure_index.json"
PROM = ROOTS["cloud"] / "observability/prometheus/week15_temporal_alignment_eval_v1_three_repo_closure_metrics.prom"

def git(repo: Path, args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()

def porcelain_lines(repo: Path) -> list[str]:
    raw = git(repo, ["status", "--porcelain=v1", "-uall"])
    return raw.splitlines() if raw else []

def status_path(line: str) -> str:
    # porcelain v1: XY<space>path, rename may contain "old -> new"; keep the final path.
    p = line[3:] if len(line) > 3 else ""
    if " -> " in p:
        p = p.split(" -> ")[-1]
    return p.strip().strip('"')

def is_cloud_self_artifact(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in CLOUD_SELF_ARTIFACT_PREFIXES)

def repo_info(name: str, repo: Path) -> dict:
    lines = porcelain_lines(repo)
    if name == "cloud":
        relevant_dirty = [line for line in lines if not is_cloud_self_artifact(status_path(line))]
        excluded_self_dirty = [line for line in lines if is_cloud_self_artifact(status_path(line))]
    else:
        relevant_dirty = lines
        excluded_self_dirty = []

    return {
        "path": str(repo),
        "head": git(repo, ["rev-parse", "--short", "HEAD"]),
        "originMain": git(repo, ["rev-parse", "--short", "origin/main"]),
        "aheadBehind": git(repo, ["rev-list", "--left-right", "--count", "HEAD...origin/main"]).replace("\t", " "),
        "porcelainCount": len(relevant_dirty),
        "rawPorcelainCount": len(lines),
        "excludedSelfArtifactDirtyCount": len(excluded_self_dirty),
        "relevantDirtyLines": relevant_dirty,
        "excludedSelfArtifactDirtyLines": excluded_self_dirty,
        "latestCommit": git(repo, ["log", "--oneline", "-1"]),
    }

def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

repos = {name: repo_info(name, path) for name, path in ROOTS.items()}
loaded = {name: load(path) for name, path in ARTIFACTS.items()}

mainbase = loaded["mainbaseExplicitRiskContract"]
java = loaded["javaExplicitRiskConsumerReport"]
cloud_gate = loaded["cloudJavaContractPlatformGate"]
cloud_dash = loaded["cloudJavaContractDashboardReady"]

failures = []

for name, info in repos.items():
    if info["porcelainCount"] != 0:
        failures.append(f"{name.upper()}_DIRTY")
    if info["aheadBehind"] != "0 0":
        failures.append(f"{name.upper()}_NOT_SYNCED:{info['aheadBehind']}")

if mainbase.get("decision") != "PASS":
    failures.append("MAINBASE_EXPLICIT_RISK_CONTRACT_NOT_PASS")
if java.get("decision") != "PASS":
    failures.append("JAVA_EXPLICIT_RISK_CONSUMER_NOT_PASS")
if cloud_gate.get("decision") != "PASS_JAVA_EXPLICIT_RISK_CONTRACT_PLATFORM_GATE":
    failures.append("CLOUD_JAVA_CONTRACT_PLATFORM_GATE_NOT_PASS")
if cloud_dash.get("decision") != "PASS":
    failures.append("CLOUD_JAVA_CONTRACT_DASHBOARD_NOT_PASS")
if cloud_dash.get("preferredSourceMode") != "java_explicit_risk_contract":
    failures.append("CLOUD_PREFERRED_SOURCE_MODE_NOT_JAVA_EXPLICIT")

main_summary = mainbase.get("summary") or {}
java_summary = java.get("summary") or {}
cloud_summary = cloud_gate.get("summary") or {}
dash_summary = cloud_dash.get("summary") or {}

expected_actionable = ["procedural_v0_0004", "procedural_v0_0010"]

if main_summary.get("actionableRiskCandidateIds") != expected_actionable:
    failures.append("MAINBASE_ACTIONABLE_SET_UNEXPECTED")
if java_summary.get("actionableRiskCandidateIds") != expected_actionable:
    failures.append("JAVA_ACTIONABLE_SET_UNEXPECTED")
if cloud_summary.get("actionableRiskCandidateIds") != expected_actionable:
    failures.append("CLOUD_GATE_ACTIONABLE_SET_UNEXPECTED")
if dash_summary.get("actionableRiskCandidateIds") != expected_actionable:
    failures.append("CLOUD_DASHBOARD_ACTIONABLE_SET_UNEXPECTED")

decision = (
    "PASS_WEEK15_TEMPORAL_ALIGNMENT_EVAL_V1_THREE_REPO_CLOSURE"
    if not failures
    else "FAIL_WEEK15_TEMPORAL_ALIGNMENT_EVAL_V1_THREE_REPO_CLOSURE"
)

report = {
    "schemaVersion": "week15.temporal_alignment.eval_v1.three_repo_closure_index.v2",
    "generatedAt": datetime.now(timezone.utc).isoformat(),
    "scope": "repository evidence closure only; closure self-artifacts are excluded from Cloud dirty detection; no live service, live Grafana, production SLO, human-review pass, semantic audio quality pass, or final mix readiness claim",
    "decision": decision,
    "failures": failures,
    "preferredSourceMode": "java_explicit_risk_contract",
    "repositories": repos,
    "artifacts": {name: str(path) for name, path in ARTIFACTS.items()},
    "closureSelfArtifactPolicy": {
        "cloudSelfArtifactPrefixes": CLOUD_SELF_ARTIFACT_PREFIXES,
        "rationale": "The closure script, report, metrics, and log are generated by this closure action and must not make the closure fail as CLOUD_DIRTY."
    },
    "summary": {
        "mainbaseDecision": mainbase.get("decision"),
        "javaDecision": java.get("decision"),
        "cloudPlatformGateDecision": cloud_gate.get("decision"),
        "cloudDashboardReadyDecision": cloud_dash.get("decision"),
        "javaApiEndpoint": java.get("apiEndpoint"),
        "candidateTotal": main_summary.get("candidateTotal"),
        "actionableRiskCandidateIds": expected_actionable,
        "nonActionableCandidateCount": len(java_summary.get("nonActionableCandidateIds") or []),
        "preferredSourceMode": "java_explicit_risk_contract",
        "legacySourceMode": "cloud_inferred_taxonomy",
    },
    "allowedClaims": [
        "Week15 Temporal Alignment Eval V1 has a repository-evidence closure across Mainbase, Java, and Cloud.",
        "Mainbase emits explicit risk/actionability fields.",
        "Java consumes and exposes the explicit risk contract.",
        "Cloud uses Java explicit risk contract as preferred dashboard and alert evidence source."
    ],
    "blockedClaims": [
        "No live Java service availability claim.",
        "No live Grafana import claim.",
        "No production SLO claim.",
        "No human-review pass claim.",
        "No semantic audio quality pass claim.",
        "No final mix readiness claim."
    ],
    "nextAction": (
        "Stop adding new Week15 gate layers today; use this closure index for weekly summary and start the next step from product-level Eval V1 handoff."
        if not failures else
        "Fix failed closure invariants before any weekly or stage summary."
    )
}

OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

PROM.write_text("\n".join([
    "# HELP week15_temporal_alignment_eval_v1_three_repo_closure_pass Three-repo closure pass flag for Week15 Eval V1.",
    "# TYPE week15_temporal_alignment_eval_v1_three_repo_closure_pass gauge",
    f'week15_temporal_alignment_eval_v1_three_repo_closure_pass{{decision="{decision}",source_mode="java_explicit_risk_contract"}} {1 if not failures else 0}',
    "# HELP week15_temporal_alignment_eval_v1_three_repo_actionable_candidate_total Actionable candidate count in three-repo closure.",
    "# TYPE week15_temporal_alignment_eval_v1_three_repo_actionable_candidate_total gauge",
    "week15_temporal_alignment_eval_v1_three_repo_actionable_candidate_total 2",
    "# HELP week15_temporal_alignment_eval_v1_three_repo_non_actionable_candidate_total Non-actionable candidate count in three-repo closure.",
    "# TYPE week15_temporal_alignment_eval_v1_three_repo_non_actionable_candidate_total gauge",
    f"week15_temporal_alignment_eval_v1_three_repo_non_actionable_candidate_total {len(java_summary.get('nonActionableCandidateIds') or [])}",
]) + "\n", encoding="utf-8")

print(json.dumps({
    "decision": decision,
    "failures": failures,
    "preferredSourceMode": "java_explicit_risk_contract",
    "cloudRelevantPorcelainCount": repos["cloud"]["porcelainCount"],
    "cloudExcludedSelfArtifactDirtyCount": repos["cloud"]["excludedSelfArtifactDirtyCount"],
    "summary": report["summary"],
    "out": str(OUT),
    "prom": str(PROM)
}, indent=2, ensure_ascii=False))

if failures:
    raise SystemExit("THREE_REPO_CLOSURE_INDEX_FAIL")
