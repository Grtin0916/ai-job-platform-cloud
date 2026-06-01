#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path.cwd()
MANIFEST = ROOT / "artifacts" / "manifests" / "week12_crossrepo_readiness_manifest.json"

EXPECTED = {
    "mainbase_head": "4992082",
    "java_head": "18f1f23",
    "cloud_head": "48ea3a1",
    "seed_count_min": 5,
}

REQUIRED_BOUNDARY_TERMS = [
    "local/non-production",
    "remote GitHub Actions failure remains suspended",
]

REQUIRED_COMPLETION_RULE_TERMS = [
    "SUCCEEDED",
    "artifactUri",
    "evalSummaryUri",
    "qualityGateStatus",
]


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def run(cmd: list[str], cwd: Path) -> str:
    try:
        return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:
        return f"UNAVAILABLE: {exc}"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"missing manifest: {path.relative_to(ROOT)}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot parse manifest JSON: {exc}")
    if not isinstance(data, dict):
        fail("manifest root must be object")
    return data


def require_repo_aligned(data: dict[str, Any], repo_name: str) -> None:
    repo = data.get("repos", {}).get(repo_name)
    if not isinstance(repo, dict):
        fail(f"missing repos.{repo_name}")

    head = str(repo.get("head"))
    origin = str(repo.get("origin_main"))
    git_status = str(repo.get("git_status"))

    if head != origin:
        fail(f"{repo_name} HEAD != origin/main: {head} != {origin}")

    if "main...origin/main" not in git_status:
        fail(f"{repo_name} git status does not show main...origin/main: {git_status}")

    required_files = repo.get("required_files")
    if not isinstance(required_files, dict) or not required_files:
        fail(f"{repo_name} required_files missing")

    missing = [
        name
        for name, row in required_files.items()
        if not isinstance(row, dict) or row.get("exists") is not True
    ]
    if missing:
        fail(f"{repo_name} required files missing: {missing}")


def main() -> None:
    data = load_json(MANIFEST)

    status = data.get("status")
    if status not in {"PASS", "PASS_WITH_WARNINGS"}:
        fail(f"manifest status is not pass-like: {status}")

    if data.get("hard_failures"):
        fail(f"manifest has hard_failures: {data.get('hard_failures')}")

    require_repo_aligned(data, "mainbase")
    require_repo_aligned(data, "java")
    require_repo_aligned(data, "cloud")

    repos = data.get("repos", {})
    if repos["mainbase"]["head"] != EXPECTED["mainbase_head"]:
        fail(f"unexpected mainbase head: {repos['mainbase']['head']}")
    if repos["java"]["head"] != EXPECTED["java_head"]:
        fail(f"unexpected java head: {repos['java']['head']}")
    if repos["cloud"]["head"] != EXPECTED["cloud_head"]:
        fail(f"unexpected cloud head: {repos['cloud']['head']}")

    readiness = data.get("readiness")
    if not isinstance(readiness, dict):
        fail("missing readiness object")

    mainbase = readiness.get("mainbase_blueprint_contract", {})
    java = readiness.get("java_completion_semantics", {})
    cloud = readiness.get("cloud_local_evidence_boundary", {})

    seed_count = mainbase.get("seed_count")
    if not isinstance(seed_count, int) or seed_count < EXPECTED["seed_count_min"]:
        fail(f"seed_count below expected minimum: {seed_count}")

    if mainbase.get("validation_status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        fail(f"unexpected mainbase validation_status: {mainbase.get('validation_status')}")

    if java.get("ready") is not True:
        fail("java readiness is not true")

    completion_rule = str(java.get("completion_rule", ""))
    for term in REQUIRED_COMPLETION_RULE_TERMS:
        if term not in completion_rule:
            fail(f"completion_rule missing term: {term}")

    if cloud.get("ready") is not True:
        fail("cloud readiness is not true")

    boundary = str(cloud.get("boundary", ""))
    for term in REQUIRED_BOUNDARY_TERMS:
        if term not in boundary:
            fail(f"cloud boundary missing term: {term}")

    next_action = str(data.get("next_system_action", {}).get("recommended", ""))
    if "remote CI" in next_action and "not" not in next_action.lower():
        fail("next action appears to re-open remote CI debugging")

    print("[PASS] Week12 cross-repo readiness gate")
    print(f"manifest={MANIFEST.relative_to(ROOT)}")
    print(f"status={status}")
    print(f"mainbase_head={repos['mainbase']['head']}")
    print(f"java_head={repos['java']['head']}")
    print(f"cloud_head={repos['cloud']['head']}")
    print(f"seed_count={seed_count}")
    print(f"validation_status={mainbase.get('validation_status')}")
    print("completion_rule=" + completion_rule)
    print("cloud_boundary=" + boundary)
    print("cloud_git_status=" + run(["git", "status", "-sb"], ROOT))


if __name__ == "__main__":
    main()