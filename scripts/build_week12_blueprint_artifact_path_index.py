#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def jsonl_count(path: Path) -> int | None:
    if not path.exists():
        return None
    count = 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def csv_count(path: Path) -> int | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return 0
    return max(0, len(rows) - 1)


def file_card(path: Path, role: str, logical_uri: str) -> dict[str, Any]:
    exists = path.exists()
    return {
        "role": role,
        "logicalUri": logical_uri,
        "absolutePath": str(path),
        "exists": exists,
        "sizeBytes": path.stat().st_size if exists and path.is_file() else None,
        "sha256": sha256_file(path) if exists and path.is_file() else None,
    }


def main() -> int:
    mainbase_root = Path.home() / "work" / "audio_engineering_repo_skeleton_v1"
    java_root = Path.home() / "work" / "media-task-platform-java"
    cloud_root = Path.home() / "work" / "ai-job-platform-cloud"

    out_dir = cloud_root / "loadtest" / "reports"
    log_dir = cloud_root / "artifacts" / "logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    runtime_index_path = cloud_root / "loadtest/reports/week12_asset_blueprint_runtime_index.json"
    runtime_index = read_json(runtime_index_path)

    paths = {
        "summary": mainbase_root / "artifacts/manifests/week12_blueprint_v1_final_summary.json",
        "manifest": mainbase_root / "artifacts/manifests/week12_blueprint_v1_manifest.json",
        "timeline_jsonl": mainbase_root / "artifacts/manifests/week12_event_timeline.jsonl",
        "timeline_csv": mainbase_root / "artifacts/manifests/week12_event_timeline.csv",
        "semantic_report": mainbase_root / "artifacts/manifests/week12_blueprint_v1_semantic_report.json",
        "validation_report": mainbase_root / "artifacts/manifests/week12_blueprint_v1_validation_report.json",
        "contact_sheet_png": mainbase_root / "artifacts/visuals/week12_event_timeline_contact_sheet.png",
        "contact_sheet_svg": mainbase_root / "artifacts/visuals/week12_event_timeline_contact_sheet.svg",
    }

    summary = read_json(paths["summary"])
    manifest = read_json(paths["manifest"])

    cards = {
        name: file_card(
            path,
            role=name,
            logical_uri=f"mainbase://week12/blueprint-v1/{path.name}",
        )
        for name, path in paths.items()
    }

    required = ["summary", "manifest", "timeline_jsonl", "timeline_csv", "contact_sheet_png"]
    required_exists = {name: cards[name]["exists"] for name in required}

    blueprint_count = None
    event_count = None
    error_count = None
    if isinstance(summary, dict):
        blueprint_count = summary.get("blueprint_count")
        event_count = summary.get("event_count")
        error_count = summary.get("error_count")

    timeline_jsonl_rows = jsonl_count(paths["timeline_jsonl"])
    timeline_csv_rows = csv_count(paths["timeline_csv"])

    runtime_status = runtime_index.get("status") if isinstance(runtime_index, dict) else None
    runtime_blocker = None
    if isinstance(runtime_index, dict):
        runtime_blocker = runtime_index.get("java", {}).get("runtimeBlocker")

    mainbase_artifacts_pass = (
        all(required_exists.values())
        and blueprint_count == 5
        and event_count == 10
        and error_count == 0
        and timeline_jsonl_rows == 10
        and timeline_csv_rows == 10
    )

    if mainbase_artifacts_pass and runtime_status == "BLOCKED_BY_JAVA_RUNTIME":
        status = "READY_FOR_CLOUD_ARTIFACT_CONSUMPTION_WITH_JAVA_RUNTIME_BLOCKED"
    elif mainbase_artifacts_pass:
        status = "READY_FOR_CLOUD_ARTIFACT_CONSUMPTION"
    else:
        status = "FAIL"

    report = {
        "schemaVersion": "week12.blueprint-artifact-path-index.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "purpose": "Expose Mainbase Blueprint V1 artifacts as a Cloud-consumable artifact path catalog for dashboard, worker, or local/k8s volume mapping.",
        "heads": {
            "mainbase": None,
            "java": None,
            "cloud": None,
        },
        "sourceRuntimeIndex": {
            "path": str(runtime_index_path),
            "exists": runtime_index_path.exists(),
            "status": runtime_status,
            "javaRuntimeBlocker": runtime_blocker,
        },
        "mainbaseArtifactGate": {
            "status": "PASS" if mainbase_artifacts_pass else "FAIL",
            "blueprintCount": blueprint_count,
            "eventCount": event_count,
            "errorCount": error_count,
            "timelineJsonlRows": timeline_jsonl_rows,
            "timelineCsvRows": timeline_csv_rows,
            "requiredExists": required_exists,
        },
        "artifactCatalog": cards,
        "cloudPathMapping": {
            "localSourceRoot": str(mainbase_root),
            "cloudConsumerRoot": "/workspace/mainbase",
            "k8sSuggestedMountPath": "/mnt/soundlayer-artifacts/mainbase",
            "env": {
                "SOUNDLAYER_BLUEPRINT_MANIFEST": "/mnt/soundlayer-artifacts/mainbase/artifacts/manifests/week12_blueprint_v1_manifest.json",
                "SOUNDLAYER_EVENT_TIMELINE_JSONL": "/mnt/soundlayer-artifacts/mainbase/artifacts/manifests/week12_event_timeline.jsonl",
                "SOUNDLAYER_EVENT_TIMELINE_CSV": "/mnt/soundlayer-artifacts/mainbase/artifacts/manifests/week12_event_timeline.csv",
                "SOUNDLAYER_CONTACT_SHEET": "/mnt/soundlayer-artifacts/mainbase/artifacts/visuals/week12_event_timeline_contact_sheet.png",
            },
        },
        "doesNotClaim": [
            "Java runtime HTTP success",
            "audio generation",
            "production Kubernetes volume mounted",
            "k6 load test",
            "Grafana dashboard already wired",
        ],
        "nextAction": "Use this artifact path index as Cloud dashboard-ready input, then either fix Java runtime blocker or expose a lightweight artifact registry contract.",
    }

    import subprocess

    for key, root in [
        ("mainbase", mainbase_root),
        ("java", java_root),
        ("cloud", cloud_root),
    ]:
        try:
            report["heads"][key] = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=root,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception:
            report["heads"][key] = None

    out_path = out_dir / "week12_blueprint_artifact_path_index.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    log_path = log_dir / f"week12_blueprint_artifact_path_index_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path.write_text(
        "\n".join(
            [
                f"status={status}",
                f"mainbase_artifacts_pass={mainbase_artifacts_pass}",
                f"timeline_jsonl_rows={timeline_jsonl_rows}",
                f"timeline_csv_rows={timeline_csv_rows}",
                f"runtime_status={runtime_status}",
                f"out_path={out_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"status={status}")
    print(f"mainbase_artifacts_pass={mainbase_artifacts_pass}")
    print(f"timeline_jsonl_rows={timeline_jsonl_rows}")
    print(f"timeline_csv_rows={timeline_csv_rows}")
    print(f"runtime_status={runtime_status}")
    print(f"out_path={out_path}")
    print(f"log_path={log_path}")

    return 0 if status.startswith("READY_FOR_CLOUD_ARTIFACT_CONSUMPTION") else 2


if __name__ == "__main__":
    raise SystemExit(main())