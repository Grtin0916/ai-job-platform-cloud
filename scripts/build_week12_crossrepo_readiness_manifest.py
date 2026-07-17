#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


CLOUD_ROOT = Path.cwd()
MAINBASE_ROOT = Path.home() / "work" / "grt_work" / "audio_engineering_repo_skeleton_v1"
JAVA_ROOT = Path.home() / "work" / "grt_work" / "media-task-platform-java"

OUT = CLOUD_ROOT / "artifacts" / "manifests" / "week12_crossrepo_readiness_manifest.json"
LOG_DIR = CLOUD_ROOT / "artifacts" / "logs"

MAINBASE_REQUIRED = {
    "blueprint_seed_manifest": MAINBASE_ROOT / "artifacts" / "manifests" / "week12_blueprint_seed_manifest.json",
    "blueprint_schema": MAINBASE_ROOT / "schemas" / "soundlayer_blueprint_seed_v0.schema.json",
    "blueprint_validation_report": MAINBASE_ROOT / "artifacts" / "manifests" / "week12_blueprint_seed_validation_report.json",
}

JAVA_REQUIRED = {
    "lifecycle_state": JAVA_ROOT / "src" / "main" / "java" / "com" / "ryan" / "media" / "model" / "MediaTaskLifecycleState.java",
    "lifecycle_transition": JAVA_ROOT / "src" / "main" / "java" / "com" / "ryan" / "media" / "model" / "MediaTaskLifecycleTransition.java",
    "completion_gate": JAVA_ROOT / "src" / "main" / "java" / "com" / "ryan" / "media" / "model" / "MediaTaskCompletionGate.java",
    "evidence_links": JAVA_ROOT / "src" / "main" / "java" / "com" / "ryan" / "media" / "model" / "MediaTaskEvidenceLinks.java",
    "completion_decision": JAVA_ROOT / "src" / "main" / "java" / "com" / "ryan" / "media" / "service" / "MediaTaskCompletionDecision.java",
    "completion_service": JAVA_ROOT / "src" / "main" / "java" / "com" / "ryan" / "media" / "service" / "MediaTaskCompletionService.java",
}

CLOUD_REQUIRED = {
    "k6_evidence_index": CLOUD_ROOT / "loadtest" / "reports" / "week11_k6_evidence_index.json",
    "k6_week11_doc": CLOUD_ROOT / "docs" / "benchmarks" / "cloud_k6_week11.md",
    "ci_validate": CLOUD_ROOT / "scripts" / "ci_validate.sh",
}


def run(cmd: list[str], cwd: Path) -> str:
    try:
        return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:
        return f"UNAVAILABLE: {exc}"


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def rel_or_abs(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def file_state(paths: dict[str, Path], root: Path) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "path": rel_or_abs(path, root),
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else None,
        }
        for name, path in paths.items()
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    blueprint = load_json(MAINBASE_REQUIRED["blueprint_seed_manifest"])
    validation = load_json(MAINBASE_REQUIRED["blueprint_validation_report"])
    k6_index = load_json(CLOUD_REQUIRED["k6_evidence_index"])

    hard_failures: list[str] = []
    warnings: list[str] = []

    for group_name, paths in [
        ("mainbase", MAINBASE_REQUIRED),
        ("java", JAVA_REQUIRED),
        ("cloud", CLOUD_REQUIRED),
    ]:
        for name, path in paths.items():
            if not path.exists():
                hard_failures.append(f"missing {group_name}.{name}: {path}")

    seed_count = None
    quality_proxy_min = None
    quality_proxy_max = None
    if isinstance(blueprint, dict):
        summary = blueprint.get("summary", {})
        seed_count = summary.get("seed_count")
        quality_proxy_min = summary.get("quality_proxy_min")
        quality_proxy_max = summary.get("quality_proxy_max")
        if seed_count is None or int(seed_count) < 5:
            warnings.append("Mainbase seed_count below expected Week12 baseline of 5")
        if summary.get("has_artifact_links") is not True:
            hard_failures.append("Mainbase blueprint seeds do not all expose artifact links")
        if summary.get("has_mainbase_eval_summary_links") is not True:
            hard_failures.append("Mainbase blueprint seeds do not all expose mainbase eval summary links")
    else:
        hard_failures.append("cannot parse Mainbase blueprint seed manifest")

    validation_status = None
    if isinstance(validation, dict):
        validation_status = validation.get("summary", {}).get("status")
        failure_count = validation.get("summary", {}).get("failure_count")
        if failure_count != 0:
            hard_failures.append(f"Mainbase validation failure_count is not 0: {failure_count}")
    else:
        hard_failures.append("cannot parse Mainbase blueprint validation report")

    k6_text = json.dumps(k6_index, ensure_ascii=False).lower() if k6_index is not None else ""
    for token in ["artifacturi", "evalsummaryuri", "qualitygatestatus", "http_req_failed", "http_req_duration"]:
        if token not in k6_text:
            warnings.append(f"Cloud k6 evidence index does not mention expected token: {token}")

    status = "PASS" if not hard_failures else "FAIL"
    if status == "PASS" and warnings:
        status = "PASS_WITH_WARNINGS"

    manifest = {
        "schema_version": "week12_crossrepo_readiness_manifest_v0",
        "generated_at_local": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "repos": {
            "mainbase": {
                "root": str(MAINBASE_ROOT),
                "git_status": run(["git", "status", "-sb"], MAINBASE_ROOT),
                "head": run(["git", "rev-parse", "--short", "HEAD"], MAINBASE_ROOT),
                "origin_main": run(["git", "rev-parse", "--short", "origin/main"], MAINBASE_ROOT),
                "required_files": file_state(MAINBASE_REQUIRED, MAINBASE_ROOT),
            },
            "java": {
                "root": str(JAVA_ROOT),
                "git_status": run(["git", "status", "-sb"], JAVA_ROOT),
                "head": run(["git", "rev-parse", "--short", "HEAD"], JAVA_ROOT),
                "origin_main": run(["git", "rev-parse", "--short", "origin/main"], JAVA_ROOT),
                "required_files": file_state(JAVA_REQUIRED, JAVA_ROOT),
            },
            "cloud": {
                "root": str(CLOUD_ROOT),
                "git_status": run(["git", "status", "-sb"], CLOUD_ROOT),
                "head": run(["git", "rev-parse", "--short", "HEAD"], CLOUD_ROOT),
                "origin_main": run(["git", "rev-parse", "--short", "origin/main"], CLOUD_ROOT),
                "required_files": file_state(CLOUD_REQUIRED, CLOUD_ROOT),
            },
        },
        "readiness": {
            "mainbase_blueprint_contract": {
                "ready": isinstance(blueprint, dict) and not any("Mainbase" in x for x in hard_failures),
                "seed_count": seed_count,
                "quality_proxy_min": quality_proxy_min,
                "quality_proxy_max": quality_proxy_max,
                "validation_status": validation_status,
            },
            "java_completion_semantics": {
                "ready": all(path.exists() for path in JAVA_REQUIRED.values()),
                "expected_states": ["CREATED", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED"],
                "completion_rule": "SUCCEEDED requires artifactUri + evalSummaryUri + qualityGateStatus",
                "service_adapter": "MediaTaskCompletionService.decideCompletionExposure",
            },
            "cloud_local_evidence_boundary": {
                "ready": all(path.exists() for path in CLOUD_REQUIRED.values()),
                "boundary": "local/non-production k6 evidence only; remote GitHub Actions failure remains suspended",
            },
        },
        "next_system_action": {
            "recommended": "Build Cloud local readiness gate or dashboard from this manifest, not from remote CI state.",
            "non_goals": [
                "Do not claim production SLO.",
                "Do not claim real cloud deployment.",
                "Do not re-open GitHub Actions remote runner debugging today.",
            ],
        },
        "hard_failures": hard_failures,
        "warnings": warnings,
    }

    OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"week12_crossrepo_readiness_manifest_{stamp}.log"
    log_path.write_text(
        "\n".join([
            "===== Week12 Cross-Repo Readiness Manifest =====",
            f"status={status}",
            f"output={OUT.relative_to(CLOUD_ROOT)}",
            f"mainbase_head={manifest['repos']['mainbase']['head']}",
            f"java_head={manifest['repos']['java']['head']}",
            f"cloud_head={manifest['repos']['cloud']['head']}",
            f"seed_count={seed_count}",
            f"validation_status={validation_status}",
            f"hard_failures={hard_failures}",
            f"warnings={warnings}",
        ]) + "\n",
        encoding="utf-8",
    )

    print(f"[{status}] Week12 cross-repo readiness manifest")
    print(f"output={OUT.relative_to(CLOUD_ROOT)}")
    print(f"log={log_path.relative_to(CLOUD_ROOT)}")
    print(f"mainbase_head={manifest['repos']['mainbase']['head']}")
    print(f"java_head={manifest['repos']['java']['head']}")
    print(f"cloud_head={manifest['repos']['cloud']['head']}")
    print(f"seed_count={seed_count}")
    print(f"validation_status={validation_status}")
    print(f"hard_failures={len(hard_failures)}")
    print(f"warnings={len(warnings)}")

    if hard_failures:
        for item in hard_failures:
            print(f"HARD_FAILURE: {item}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()