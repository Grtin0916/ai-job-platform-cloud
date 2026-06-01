#!/usr/bin/env python3
"""
Build Week12 Cloud-side asset-blueprint endpoint index.

Purpose:
- Consume the finalized Mainbase Blueprint V1 artifact.
- Consume the Java asset-blueprint HTTP endpoint contract.
- Emit a Cloud-side structured index for later loadtest/dashboard/runbook wiring.

Boundary:
- No Docker/kind/k6 execution.
- No production endpoint claim.
- This only records and validates local cross-repo handoff facts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(cmd: List[str], cwd: Path) -> str:
    return subprocess.check_output(cmd, cwd=str(cwd), text=True).strip()


def git_head(repo: Path) -> str:
    return run(["git", "rev-parse", "--short", "HEAD"], repo)


def git_status(repo: Path) -> str:
    return run(["git", "status", "-sb"], repo)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def file_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def latest_file(pattern: str, root: Path) -> Path | None:
    files = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def collect_blueprint_summary(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for bp in manifest.get("blueprints", []):
        scene = bp.get("scene", {})
        events = bp.get("events", [])
        rows.append(
            {
                "blueprint_id": bp.get("blueprint_id"),
                "source_seed_id": bp.get("source_seed_id"),
                "scene_description": scene.get("description"),
                "semantic_tags": scene.get("semantic_tags", []),
                "event_count": len(events),
                "event_labels": [e.get("label") for e in events],
                "blueprint_artifact_uri": bp.get("artifacts", {}).get("blueprint_artifact_uri"),
                "timeline_jsonl_uri": bp.get("artifacts", {}).get("timeline_jsonl_uri"),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mainbase",
        type=Path,
        default=Path(os.environ.get("MAINBASE", str(Path.home() / "work/audio_engineering_repo_skeleton_v1"))),
    )
    parser.add_argument(
        "--java",
        type=Path,
        default=Path(os.environ.get("JAVA", str(Path.home() / "work/media-task-platform-java"))),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("loadtest/reports/week12_asset_blueprint_endpoint_index.json"),
    )
    args = parser.parse_args()

    cloud = Path.cwd()
    errors: List[str] = []
    warnings: List[str] = []

    mainbase = args.mainbase
    java = args.java

    mainbase_manifest_path = mainbase / "artifacts/manifests/week12_blueprint_v1_manifest.json"
    mainbase_summary_path = mainbase / "artifacts/manifests/week12_blueprint_v1_final_summary.json"
    mainbase_timeline_jsonl = mainbase / "artifacts/manifests/week12_event_timeline.jsonl"
    mainbase_timeline_csv = mainbase / "artifacts/manifests/week12_event_timeline.csv"
    mainbase_schema = mainbase / "schemas/soundlayer_blueprint_v1.schema.json"
    mainbase_contact_sheet = mainbase / "artifacts/visuals/week12_event_timeline_contact_sheet.png"

    java_controller = java / "src/main/java/com/ryan/media/api/MediaTaskAssetBlueprintController.java"
    java_binding = java / "src/main/java/com/ryan/media/model/MediaTaskAssetBlueprintBinding.java"
    java_view = java / "src/main/java/com/ryan/media/model/MediaTaskAssetBlueprintView.java"
    java_controller_test = java / "src/test/java/com/ryan/media/MediaTaskAssetBlueprintControllerTest.java"
    java_latest_http_log = latest_file("artifacts/logs/week12_asset_blueprint_controller_http_*.log", java)

    required_files = [
        mainbase_manifest_path,
        mainbase_summary_path,
        mainbase_timeline_jsonl,
        mainbase_timeline_csv,
        mainbase_schema,
        mainbase_contact_sheet,
        java_controller,
        java_binding,
        java_view,
        java_controller_test,
    ]
    for p in required_files:
        if not p.exists():
            errors.append(f"missing required file: {p}")

    mainbase_manifest: Dict[str, Any] = {}
    mainbase_final_summary: Dict[str, Any] = {}
    if mainbase_manifest_path.exists():
        mainbase_manifest = read_json(mainbase_manifest_path)
        summary = mainbase_manifest.get("summary", {})
        if summary.get("status") != "PASS":
            errors.append("mainbase blueprint manifest summary.status is not PASS")
        if summary.get("blueprint_count") != 5:
            errors.append("mainbase blueprint_count is not 5")
        if summary.get("event_count") != 10:
            errors.append("mainbase event_count is not 10")
        if summary.get("finalized") is not True:
            errors.append("mainbase blueprint manifest is not finalized")

    if mainbase_summary_path.exists():
        mainbase_final_summary = read_json(mainbase_summary_path)
        if mainbase_final_summary.get("status") != "PASS":
            errors.append("mainbase final summary status is not PASS")
        if mainbase_final_summary.get("error_count") != 0:
            errors.append("mainbase final summary has errors")

    controller_text = file_text(java_controller) if java_controller.exists() else ""
    controller_test_text = file_text(java_controller_test) if java_controller_test.exists() else ""
    http_log_text = file_text(java_latest_http_log) if java_latest_http_log else ""

    endpoint_path = "/api/media-tasks/{taskId}/asset-blueprint"
    if endpoint_path not in controller_text:
        errors.append("java controller does not expose expected endpoint path")
    if "@GetMapping" not in controller_text:
        errors.append("java controller missing @GetMapping")
    if "MockMvc" not in controller_test_text:
        errors.append("java controller test missing MockMvc")
    if "jsonPath" not in controller_test_text:
        errors.append("java controller test missing jsonPath assertions")

    if java_latest_http_log is None:
        errors.append("missing Java controller HTTP evidence log")
    else:
        if "Tests run: 19, Failures: 0, Errors: 0" not in http_log_text:
            errors.append("Java asset-blueprint aggregate test count is not 19/0/0 in latest HTTP log")
        if "BUILD SUCCESS" not in http_log_text:
            errors.append("Java latest HTTP log does not show BUILD SUCCESS")

    try:
        heads = {
            "mainbase": git_head(mainbase),
            "java": git_head(java),
            "cloud": git_head(cloud),
        }
        statuses = {
            "mainbase": git_status(mainbase),
            "java": git_status(java),
            "cloud": git_status(cloud),
        }
    except Exception as exc:
        errors.append(f"failed to read git truth: {exc}")
        heads = {}
        statuses = {}

    java_response_fields = [
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

    for field in java_response_fields:
        if field not in controller_test_text and field not in file_text(java_view):
            warnings.append(f"response field not directly found in view/test text: {field}")

    index = {
        "schema_version": "week12_asset_blueprint_endpoint_index_v1",
        "created_at": now_iso(),
        "status": "PASS" if not errors else "FAIL",
        "repos": {
            "mainbase": {
                "path": str(mainbase),
                "head": heads.get("mainbase"),
                "status": statuses.get("mainbase"),
            },
            "java": {
                "path": str(java),
                "head": heads.get("java"),
                "status": statuses.get("java"),
            },
            "cloud": {
                "path": str(cloud),
                "head": heads.get("cloud"),
                "status": statuses.get("cloud"),
            },
        },
        "mainbase_blueprint_v1": {
            "manifest_path": str(mainbase_manifest_path),
            "final_summary_path": str(mainbase_summary_path),
            "schema_path": str(mainbase_schema),
            "timeline_jsonl_path": str(mainbase_timeline_jsonl),
            "timeline_csv_path": str(mainbase_timeline_csv),
            "contact_sheet_path": str(mainbase_contact_sheet),
            "manifest_summary": mainbase_manifest.get("summary", {}),
            "final_summary": {
                "status": mainbase_final_summary.get("status"),
                "blueprint_count": mainbase_final_summary.get("blueprint_count"),
                "event_count": mainbase_final_summary.get("event_count"),
                "error_count": mainbase_final_summary.get("error_count"),
                "warning_count": mainbase_final_summary.get("warning_count"),
            },
            "blueprints": collect_blueprint_summary(mainbase_manifest),
        },
        "java_asset_blueprint_endpoint": {
            "controller_path": str(java_controller),
            "binding_path": str(java_binding),
            "view_path": str(java_view),
            "controller_test_path": str(java_controller_test),
            "latest_http_log": str(java_latest_http_log) if java_latest_http_log else None,
            "method": "GET",
            "path": endpoint_path,
            "default_input_asset_uri": "file://samples/week12/city_walk.mp4",
            "default_blueprint_id": "blueprint_v1_66d315251e",
            "default_quality_gate_status": "PASS",
            "query_params": [
                "inputAssetUri",
                "blueprintId",
                "qualityGateStatus",
            ],
            "response_fields": java_response_fields,
            "mockmvc_covered": "MockMvc" in controller_test_text and "jsonPath" in controller_test_text,
            "test_evidence": {
                "aggregate_expected": "Tests run: 19, Failures: 0, Errors: 0",
                "aggregate_found": "Tests run: 19, Failures: 0, Errors: 0" in http_log_text,
                "build_success_found": "BUILD SUCCESS" in http_log_text,
            },
        },
        "cloud_handoff": {
            "purpose": "Cloud-side index for later loadtest, dashboard, runbook, or artifact-path readiness wiring.",
            "non_goals": [
                "No production endpoint availability claim",
                "No Docker/kind/k6 execution in this step",
                "No object-store retention or signed URL lifecycle guarantee",
            ],
            "next_candidate_actions": [
                "wire index into a lightweight Cloud readiness check",
                "add optional k6 smoke only after endpoint is served by a running Java app",
                "surface artifact path fields in dashboard/runbook after index is stable",
            ],
        },
        "errors": errors,
        "warnings": warnings,
    }

    write_json(args.out, index)

    print("[PASS]" if index["status"] == "PASS" else "[FAIL]", "Week12 Cloud asset-blueprint endpoint index")
    print(f"status={index['status']}")
    print(f"mainbase_head={heads.get('mainbase')}")
    print(f"java_head={heads.get('java')}")
    print(f"cloud_head={heads.get('cloud')}")
    print(f"blueprint_count={mainbase_manifest.get('summary', {}).get('blueprint_count')}")
    print(f"event_count={mainbase_manifest.get('summary', {}).get('event_count')}")
    print(f"endpoint={endpoint_path}")
    print(f"mockmvc_covered={index['java_asset_blueprint_endpoint']['mockmvc_covered']}")
    print(f"errors={len(errors)}")
    print(f"warnings={len(warnings)}")
    print(f"out={args.out}")

    return 0 if index["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())