from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CLOUD = Path(os.environ.get("CLOUD", Path.cwd())).resolve()
MAINBASE = Path(os.environ.get("MAINBASE", "~/work/audio_engineering_repo_skeleton_v1")).expanduser().resolve()
JAVA = Path(os.environ.get("JAVA", "~/work/media-task-platform-java")).expanduser().resolve()

OUT_JSON = CLOUD / "loadtest/reports/week16_s3_failure_taxonomy_closure_index.json"
OUT_METRICS = CLOUD / "observability/prometheus/week16_s3_failure_taxonomy_closure_metrics.prom"

MAINBASE_REPORT = MAINBASE / "artifacts/evals/week16_temporal_alignment_failure_regression_report.json"
JAVA_REPORT = JAVA / "artifacts/manifests/week16_java_temporal_alignment_rerun_plan_report.json"
CLOUD_REPORT = CLOUD / "loadtest/reports/week16_failure_taxonomy_fault_drill.json"

EXPECTED_BLOCKED_CLAIMS = {
    "semantic_audio_quality_pass_not_verified",
    "human_review_pass_not_verified",
    "final_mix_readiness_not_verified",
    "live_java_service_availability_not_verified",
    "live_prometheus_or_grafana_import_not_verified",
    "production_slo_or_real_cloud_deployment_not_verified",
}


def run_git(repo: Path, args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def git_state(
    repo: Path,
    allowed_dirty_paths: set[str] | None = None,
    allowed_dirty_prefixes: tuple[str, ...] = (),
) -> dict[str, Any]:
    allowed_dirty_paths = allowed_dirty_paths or set()

    head = run_git(repo, ["rev-parse", "--short", "HEAD"])
    origin = run_git(repo, ["rev-parse", "--short", "origin/main"])
    ahead_behind = run_git(repo, ["rev-list", "--left-right", "--count", "HEAD...origin/main"])
    normalized_ahead_behind = " ".join(ahead_behind.split())

    raw_porcelain = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "-uall"],
        cwd=repo,
        text=True,
    ).splitlines()

    def porcelain_path(line: str) -> str:
        # Porcelain v1 line format starts with two status columns plus one space.
        # For current closure outputs, paths do not include rename arrows.
        return line[3:] if len(line) >= 4 else line

    def is_allowed_current_closure_output(line: str) -> bool:
        path = porcelain_path(line)
        return path in allowed_dirty_paths or any(path.startswith(prefix) for prefix in allowed_dirty_prefixes)

    ignored_current_closure_porcelain = [
        line for line in raw_porcelain if is_allowed_current_closure_output(line)
    ]
    blocking_porcelain = [
        line for line in raw_porcelain if not is_allowed_current_closure_output(line)
    ]

    recent = run_git(repo, ["log", "--oneline", "-3"]).splitlines()

    return {
        "path": str(repo),
        "head": head,
        "originMain": origin,
        "aheadBehind": normalized_ahead_behind,
        "rawPorcelainCount": len(raw_porcelain),
        "porcelainCount": len(blocking_porcelain),
        "porcelain": blocking_porcelain,
        "ignoredCurrentClosurePorcelain": ignored_current_closure_porcelain,
        "recentCommits": recent,
        "cleanAndSynced": head == origin and normalized_ahead_behind == "0 0" and len(blocking_porcelain) == 0,
    }


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required JSON: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"expected object JSON: {path}")
    return data


def collect_blocked_claims(*reports: dict[str, Any]) -> list[str]:
    out: set[str] = set()
    for report in reports:
        summary = report.get("summary", {})
        claims = summary.get("blockedClaims", [])
        if isinstance(claims, list):
            out.update(str(x) for x in claims)

        direct = report.get("blockedClaims", [])
        if isinstance(direct, list):
            out.update(str(x) for x in direct)

        boundary = report.get("boundary", [])
        if isinstance(boundary, list):
            out.update(str(x) for x in boundary)

    return sorted(out)


def build_metrics(index: dict[str, Any]) -> str:
    lines: list[str] = []

    def emit(name: str, help_text: str, samples: list[str]) -> None:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
        lines.extend(samples)

    decision = index["decision"]
    summary = index["summary"]

    emit(
        "week16_s3_failure_taxonomy_closure_decision",
        "Week16 S3 failure taxonomy closure decision, 1 means pass.",
        [f'week16_s3_failure_taxonomy_closure_decision{{decision="{decision}"}} {1 if decision.startswith("PASS") else 0}'],
    )

    emit(
        "week16_s3_failure_taxonomy_closure_repo_synced",
        "Whether each repository is clean and synced with origin/main.",
        [
            f'week16_s3_failure_taxonomy_closure_repo_synced{{repo="{repo}"}} {1 if state["cleanAndSynced"] else 0}'
            for repo, state in index["repositories"].items()
        ],
    )

    emit(
        "week16_s3_failure_taxonomy_closure_candidate_total",
        "Candidate total from the S3 failure taxonomy chain.",
        [f"week16_s3_failure_taxonomy_closure_candidate_total {summary['candidateTotal']}"],
    )

    emit(
        "week16_s3_failure_taxonomy_closure_scenario_total",
        "Synthetic Cloud fault-drill scenario total.",
        [f"week16_s3_failure_taxonomy_closure_scenario_total {summary['scenarioTotal']}"],
    )

    emit(
        "week16_s3_failure_taxonomy_closure_alert_total",
        "Alert total by severity from Cloud fault drill.",
        [
            f'week16_s3_failure_taxonomy_closure_alert_total{{severity="critical"}} {summary["criticalAlertTotal"]}',
            f'week16_s3_failure_taxonomy_closure_alert_total{{severity="warning"}} {summary["warningAlertTotal"]}',
        ],
    )

    return "\n".join(lines) + "\n"


def main() -> None:
    mainbase_report = load_json(MAINBASE_REPORT)
    java_report = load_json(JAVA_REPORT)
    cloud_report = load_json(CLOUD_REPORT)

    cloud_allowed_dirty_paths = {
        "scripts/build_week16_s3_failure_taxonomy_closure_index.py",
        "loadtest/reports/week16_s3_failure_taxonomy_closure_index.json",
        "observability/prometheus/week16_s3_failure_taxonomy_closure_metrics.prom",
    }

    repositories = {
        "mainbase": git_state(MAINBASE),
        "java": git_state(JAVA),
        "cloud": git_state(
            CLOUD,
            allowed_dirty_paths=cloud_allowed_dirty_paths,
            allowed_dirty_prefixes=("artifacts/logs/week16_s3_failure_taxonomy_closure_",),
        ),
    }

    blocked_claims = collect_blocked_claims(mainbase_report, java_report, cloud_report)

    decision_errors: list[str] = []

    if not all(state["cleanAndSynced"] for state in repositories.values()):
        decision_errors.append("one or more repositories are not clean and synced with origin/main")

    if mainbase_report.get("decision") != "PASS_WEEK16_FAILURE_REGRESSION_REPORT_V0_EVIDENCE_DRIVEN":
        decision_errors.append("Mainbase failure regression report is not PASS evidence-driven")

    if java_report.get("decision") != "PASS_WEEK16_JAVA_RERUN_PLAN_IT":
        decision_errors.append("Java rerun-plan report is not PASS")

    if cloud_report.get("decision") != "PASS_WEEK16_FAILURE_TAXONOMY_FAULT_DRILL":
        decision_errors.append("Cloud fault drill report is not PASS")

    if java_report.get("sourceMainbaseDecision") != mainbase_report.get("decision"):
        decision_errors.append("Java report does not point to current Mainbase decision")

    if cloud_report.get("sourceJavaDecision") != java_report.get("decision"):
        decision_errors.append("Cloud report does not point to current Java decision")

    if not EXPECTED_BLOCKED_CLAIMS.issubset(set(blocked_claims)):
        decision_errors.append("blocked claims are incomplete across the chain")

    mainbase_summary = mainbase_report.get("summary", {})
    cloud_summary = cloud_report.get("summary", {})

    if int(mainbase_summary.get("candidateTotal", 0)) != 10:
        decision_errors.append("candidateTotal expected 10")
    if int(mainbase_summary.get("p1RegressionFixtureTotal", 0)) != 2:
        decision_errors.append("p1RegressionFixtureTotal expected 2")
    if int(mainbase_summary.get("thresholdFixtureTotal", 0)) != 1:
        decision_errors.append("thresholdFixtureTotal expected 1")
    if int(mainbase_summary.get("passControlTotal", 0)) != 7:
        decision_errors.append("passControlTotal expected 7")
    if int(mainbase_summary.get("evidenceGapFixtureTotal", -1)) != 0:
        decision_errors.append("evidenceGapFixtureTotal expected 0")
    if int(cloud_summary.get("scenarioTotal", 0)) != 3:
        decision_errors.append("Cloud scenarioTotal expected 3")
    if int(cloud_summary.get("criticalAlertTotal", 0)) != 1:
        decision_errors.append("Cloud criticalAlertTotal expected 1")
    if int(cloud_summary.get("warningAlertTotal", 0)) != 2:
        decision_errors.append("Cloud warningAlertTotal expected 2")

    decision = (
        "PASS_WEEK16_S3_FAILURE_TAXONOMY_CLOSURE"
        if not decision_errors
        else "FAIL_WEEK16_S3_FAILURE_TAXONOMY_CLOSURE"
    )

    index = {
        "schemaVersion": "week16.s3.failure_taxonomy_closure.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "decisionErrors": decision_errors,
        "repositories": repositories,
        "evidenceChain": {
            "mainbase": {
                "path": str(MAINBASE_REPORT),
                "decision": mainbase_report.get("decision"),
                "classificationMode": mainbase_report.get("classificationMode"),
                "summary": mainbase_report.get("summary"),
            },
            "java": {
                "path": str(JAVA_REPORT),
                "decision": java_report.get("decision"),
                "apiEndpoint": java_report.get("apiEndpoint"),
                "sourceMainbaseDecision": java_report.get("sourceMainbaseDecision"),
                "sourceClassificationMode": java_report.get("sourceClassificationMode"),
                "summary": java_report.get("summary"),
            },
            "cloud": {
                "path": str(CLOUD_REPORT),
                "decision": cloud_report.get("decision"),
                "sourceJavaDecision": cloud_report.get("sourceJavaDecision"),
                "sourceMainbaseDecision": cloud_report.get("sourceMainbaseDecision"),
                "sourceClassificationMode": cloud_report.get("sourceClassificationMode"),
                "summary": cloud_report.get("summary"),
            },
        },
        "summary": {
            "candidateTotal": int(mainbase_summary.get("candidateTotal", 0)),
            "p1RegressionFixtureTotal": int(mainbase_summary.get("p1RegressionFixtureTotal", 0)),
            "thresholdFixtureTotal": int(mainbase_summary.get("thresholdFixtureTotal", 0)),
            "passControlTotal": int(mainbase_summary.get("passControlTotal", 0)),
            "evidenceGapFixtureTotal": int(mainbase_summary.get("evidenceGapFixtureTotal", 0)),
            "scenarioTotal": int(cloud_summary.get("scenarioTotal", 0)),
            "criticalAlertTotal": int(cloud_summary.get("criticalAlertTotal", 0)),
            "warningAlertTotal": int(cloud_summary.get("warningAlertTotal", 0)),
            "blockedClaimTotal": len(blocked_claims),
            "blockedClaims": blocked_claims,
        },
        "boundary": [
            "local repository evidence closure only",
            "does not claim semantic audio quality pass",
            "does not claim human review pass",
            "does not claim final mix readiness",
            "does not claim live Java service availability",
            "does not claim live Prometheus scrape or live Grafana import",
            "does not claim production SLO or real cloud deployment",
            "does not claim async rerun worker execution",
        ],
        "artifacts": {
            "closureIndex": str(OUT_JSON.relative_to(CLOUD)),
            "closureMetrics": str(OUT_METRICS.relative_to(CLOUD)),
            "mainbaseReport": str(MAINBASE_REPORT),
            "javaReport": str(JAVA_REPORT),
            "cloudFaultDrillReport": str(CLOUD_REPORT),
        },
    }

    OUT_JSON.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_METRICS.write_text(build_metrics(index), encoding="utf-8")

    print(f"decision={decision}")
    print(f"decisionErrors={decision_errors}")
    print(f"mainbaseHead={repositories['mainbase']['head']}")
    print(f"javaHead={repositories['java']['head']}")
    print(f"cloudHead={repositories['cloud']['head']}")
    print(f"summary={index['summary']}")

    if decision_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()