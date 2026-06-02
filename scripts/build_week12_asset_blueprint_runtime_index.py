#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = [
    "taskId",
    "inputAssetUri",
    "blueprintArtifactUri",
    "blueprintId",
    "timelineArtifactUri",
    "qualityGateStatus",
    "qualityGatePassed",
    "blueprintManifestLinked",
    "timelineArtifactLinked",
]


def run(cmd: list[str], cwd: Path) -> str:
    try:
        return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def latest_file(root: Path, pattern: str) -> Path | None:
    files = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def grep_files(root: Path, patterns: list[str], include_ext: tuple[str, ...]) -> dict[str, Any]:
    hits: dict[str, list[str]] = {p: [] for p in patterns}
    scanned = 0

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", "target", "build", ".gradle"} for part in path.parts):
            continue
        if path.suffix not in include_ext and path.name not in {"README.md", "openapi.yaml"}:
            continue

        scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        rel = str(path.relative_to(root))
        for pat in patterns:
            if pat in text:
                hits[pat].append(rel)

    return {
        "scanned_files": scanned,
        "hits": {k: sorted(v)[:30] for k, v in hits.items()},
        "present": {k: bool(v) for k, v in hits.items()},
    }


def extract_blocker(java_root: Path) -> dict[str, Any]:
    runtime_log = latest_file(java_root, "artifacts/logs/week12_asset_blueprint_runtime_http_it_*.log")
    jar_log = latest_file(java_root, "artifacts/logs/week12_asset_blueprint_runtime_jar_*.log")
    app_log = latest_file(java_root, "artifacts/logs/week12_asset_blueprint_runtime_app_*.log")

    candidate_logs = [p for p in [runtime_log, jar_log, app_log] if p is not None]
    blocker = {
        "status": "UNKNOWN",
        "type": None,
        "message": None,
        "evidence_log": str(candidate_logs[0]) if candidate_logs else None,
    }

    for log in candidate_logs:
        text = log.read_text(encoding="utf-8", errors="replace")[-20000:]
        if "Unknown data type" in text and "TIMESTAMPTZ" in text:
            blocker.update(
                {
                    "status": "CONFIRMED",
                    "type": "FLYWAY_H2_POSTGRESQL_TYPE_MISMATCH",
                    "message": "Flyway migration V1__init.sql uses PostgreSQL timestamptz, but the current H2-backed runtime test context rejects it.",
                    "evidence_log": str(log),
                }
            )
            break
        if "Failed to load ApplicationContext" in text:
            blocker.update(
                {
                    "status": "CONFIRMED",
                    "type": "SPRING_APPLICATION_CONTEXT_BOOT_FAILURE",
                    "message": "Spring full application context failed before the asset-blueprint endpoint could be called.",
                    "evidence_log": str(log),
                }
            )
            break

    return blocker


def main() -> int:
    cloud_root = Path.home() / "work" / "ai-job-platform-cloud"
    mainbase_root = Path.home() / "work" / "audio_engineering_repo_skeleton_v1"
    java_root = Path.home() / "work" / "media-task-platform-java"

    out_dir = cloud_root / "loadtest" / "reports"
    log_dir = cloud_root / "artifacts" / "logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    mainbase_summary_path = mainbase_root / "artifacts/manifests/week12_blueprint_v1_final_summary.json"
    mainbase_manifest_path = mainbase_root / "artifacts/manifests/week12_blueprint_v1_manifest.json"
    mainbase_timeline_jsonl = mainbase_root / "artifacts/manifests/week12_event_timeline.jsonl"
    mainbase_timeline_csv = mainbase_root / "artifacts/manifests/week12_event_timeline.csv"
    mainbase_contact_sheet = mainbase_root / "artifacts/visuals/week12_event_timeline_contact_sheet.png"

    summary = read_json(mainbase_summary_path)
    blocker = extract_blocker(java_root)

    java_contract = grep_files(
        java_root,
        [
            "asset-blueprint",
            "MediaTaskAssetBlueprint",
            "blueprintArtifactUri",
            "timelineArtifactUri",
            "qualityGateStatus",
            "task-week12-001",
        ],
        include_ext=(".java", ".yaml", ".yml", ".md"),
    )

    artifact_paths = {
        "mainbase_summary": str(mainbase_summary_path),
        "mainbase_manifest": str(mainbase_manifest_path),
        "mainbase_timeline_jsonl": str(mainbase_timeline_jsonl),
        "mainbase_timeline_csv": str(mainbase_timeline_csv),
        "mainbase_contact_sheet": str(mainbase_contact_sheet),
    }

    artifact_exists = {k: Path(v).exists() for k, v in artifact_paths.items()}

    mainbase_pass = (
        summary is not None
        and (summary.get("status") == "PASS" or summary.get("final_status") == "PASS")
        and summary.get("blueprint_count") == 5
        and summary.get("event_count") == 10
        and summary.get("error_count") == 0
        and all(artifact_exists.values())
    )

    java_contract_present = all(java_contract["present"].values())
    runtime_pass_evidence = java_root / "artifacts/runtime/week12_asset_blueprint_runtime_http_test.json"
    runtime_evidence = read_json(runtime_pass_evidence)

    if runtime_evidence and runtime_evidence.get("status") == "PASS":
        status = "PASS"
        reason = "Java runtime HTTP evidence is available and passed."
    elif mainbase_pass and java_contract_present and blocker["status"] == "CONFIRMED":
        status = "BLOCKED_BY_JAVA_RUNTIME"
        reason = blocker["message"]
    elif mainbase_pass and java_contract_present:
        status = "READY_BUT_RUNTIME_NOT_EXECUTED"
        reason = "Mainbase artifacts and Java static contract are present, but no valid runtime HTTP evidence exists."
    else:
        status = "FAIL"
        reason = "Mainbase artifacts or Java static contract are incomplete."

    report = {
        "schemaVersion": "week12.asset-blueprint.runtime-index.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "reason": reason,
        "heads": {
            "mainbase": run(["git", "rev-parse", "--short", "HEAD"], mainbase_root),
            "java": run(["git", "rev-parse", "--short", "HEAD"], java_root),
            "cloud": run(["git", "rev-parse", "--short", "HEAD"], cloud_root),
        },
        "mainbase": {
            "status": "PASS" if mainbase_pass else "FAIL",
            "summary": summary,
            "artifactPaths": artifact_paths,
            "artifactExists": artifact_exists,
        },
        "java": {
            "staticContractStatus": "PASS" if java_contract_present else "FAIL",
            "contractSearch": java_contract,
            "runtimeEvidencePath": str(runtime_pass_evidence),
            "runtimeEvidenceExists": runtime_pass_evidence.exists(),
            "runtimeEvidence": runtime_evidence,
            "runtimeBlocker": blocker,
            "requiredRuntimeFields": REQUIRED_FIELDS,
        },
        "cloud": {
            "indexPurpose": "Record whether Mainbase Blueprint V1 artifacts are consumable through Java asset-blueprint runtime behavior.",
            "nextGate": "Fix Java runtime blocker or provide a test profile that reaches the endpoint without Flyway/H2 dialect failure.",
            "doesNotClaim": [
                "production SLO",
                "Docker or Kubernetes runtime",
                "k6 load test",
                "successful Java HTTP runtime when status is BLOCKED_BY_JAVA_RUNTIME",
            ],
        },
    }

    out_path = out_dir / "week12_asset_blueprint_runtime_index.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    log_path = log_dir / f"week12_asset_blueprint_runtime_index_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path.write_text(
        "\n".join(
            [
                f"status={status}",
                f"reason={reason}",
                f"mainbase_pass={mainbase_pass}",
                f"java_contract_present={java_contract_present}",
                f"runtime_blocker_type={blocker.get('type')}",
                f"out_path={out_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"status={status}")
    print(f"reason={reason}")
    print(f"out_path={out_path}")
    print(f"log_path={log_path}")
    print(f"mainbase_pass={mainbase_pass}")
    print(f"java_contract_present={java_contract_present}")
    print(f"runtime_blocker_type={blocker.get('type')}")

    return 0 if status in {"PASS", "BLOCKED_BY_JAVA_RUNTIME", "READY_BUT_RUNTIME_NOT_EXECUTED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())