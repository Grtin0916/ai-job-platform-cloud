#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tarfile
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_ROLES = {
    "summary",
    "manifest",
    "timeline_jsonl",
    "timeline_csv",
    "semantic_report",
    "validation_report",
    "contact_sheet_png",
    "schema",
}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing json: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def parse_sha256_line(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8").strip()
    parts = text.split()
    if len(parts) < 2:
        raise ValueError(f"bad sha256 file: {path}")
    return parts[0], parts[1]


def verify_bundle_checksums(bundle_dir: Path) -> dict[str, Any]:
    checksum_path = bundle_dir / "SHA256SUMS.txt"
    if not checksum_path.exists():
        return {"status": "FAIL", "missing": ["SHA256SUMS.txt"], "checked": 0, "failed": []}

    failed: list[str] = []
    checked = 0

    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, rel = line.split(maxsplit=1)
        target = bundle_dir / rel
        checked += 1
        if not target.exists():
            failed.append(f"{rel}: missing")
            continue
        actual = sha256_file(target)
        if actual != expected:
            failed.append(f"{rel}: expected={expected}, actual={actual}")

    return {
        "status": "PASS" if not failed else "FAIL",
        "checksumFile": str(checksum_path),
        "checked": checked,
        "failed": failed,
    }


def tar_members(tar_path: Path) -> list[str]:
    if not tar_path.exists():
        return []
    with tarfile.open(tar_path, "r:gz") as tar:
        return sorted(tar.getnames())


def panel(panel_id: int, title: str, markdown: str, x: int, y: int, w: int, h: int) -> dict[str, Any]:
    return {
        "id": panel_id,
        "type": "text",
        "title": title,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "options": {"mode": "markdown", "content": markdown},
    }


def main() -> int:
    cloud_root = Path.home() / "work" / "ai-job-platform-cloud"
    mainbase_root = Path.home() / "work" / "audio_engineering_repo_skeleton_v1"
    java_root = Path.home() / "work" / "media-task-platform-java"

    handoff_root = mainbase_root / "artifacts/exports/week12_soundlayer_blueprint_v1_cloud_handoff"
    handoff_manifest_path = handoff_root / "handoff_manifest.json"
    handoff_tar_path = mainbase_root / "artifacts/exports/week12_soundlayer_blueprint_v1_cloud_handoff.tar.gz"
    handoff_tar_sha_path = mainbase_root / "artifacts/exports/week12_soundlayer_blueprint_v1_cloud_handoff.tar.gz.sha256"

    runtime_index_path = cloud_root / "loadtest/reports/week12_asset_blueprint_runtime_index.json"
    artifact_index_path = cloud_root / "loadtest/reports/week12_blueprint_artifact_path_index.json"
    dashboard_index_path = cloud_root / "loadtest/reports/week12_dashboard_ready_index.json"
    dashboard_json_path = cloud_root / "observability/grafana/dashboards/week12_soundlayer_artifact_dashboard.json"

    log_dir = cloud_root / "artifacts/logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    runtime_index = read_json(runtime_index_path)
    handoff = read_json(handoff_manifest_path)

    files = handoff.get("files", {})
    roles = set(files.keys())
    missing_roles = sorted(REQUIRED_ROLES - roles)

    mainbase_gate = handoff.get("mainbaseGate", {})
    bundle_checksum = verify_bundle_checksums(handoff_root)

    tar_expected_sha, tar_expected_name = parse_sha256_line(handoff_tar_sha_path)
    tar_actual_sha = sha256_file(handoff_tar_path)
    tar_ok = tar_expected_sha == tar_actual_sha and tar_expected_name == handoff_tar_path.name
    tar_list = tar_members(handoff_tar_path)

    runtime_status = runtime_index.get("status")
    java_blocker = runtime_index.get("java", {}).get("runtimeBlocker", {})
    java_blocker_type = java_blocker.get("type")

    handoff_gate = {
        "handoff_manifest_exists": handoff_manifest_path.exists(),
        "handoff_status_pass": handoff.get("status") == "PASS",
        "mainbase_blueprint_count_is_5": mainbase_gate.get("blueprintCount") == 5,
        "mainbase_event_count_is_10": mainbase_gate.get("eventCount") == 10,
        "timeline_jsonl_rows_is_10": mainbase_gate.get("timelineJsonlRows") == 10,
        "timeline_csv_rows_is_10": mainbase_gate.get("timelineCsvRows") == 10,
        "required_roles_present": not missing_roles,
        "bundle_checksums_pass": bundle_checksum.get("status") == "PASS",
        "tar_exists": handoff_tar_path.exists(),
        "tar_sha256_matches": tar_ok,
        "runtime_blocker_recorded": runtime_status == "BLOCKED_BY_JAVA_RUNTIME"
        and java_blocker_type == "FLYWAY_H2_POSTGRESQL_TYPE_MISMATCH",
    }

    all_handoff_ready = all(handoff_gate.values())

    artifact_status = (
        "READY_FOR_CLOUD_HANDOFF_CONSUMPTION_WITH_JAVA_RUNTIME_BLOCKED"
        if all_handoff_ready
        else "FAIL"
    )

    now = datetime.now(timezone.utc).isoformat()

    handoff_artifact_index = {
        "schemaVersion": "week12.blueprint-artifact-path-index.v2",
        "generatedAt": now,
        "status": artifact_status,
        "purpose": "Consume Mainbase Week12 SoundLayer Blueprint V1 handoff bundle as the Cloud artifact contract.",
        "heads": {
            "mainbaseRepoHead": git_head(mainbase_root),
            "mainbaseHandoffSourceHead": handoff.get("sourceHead"),
            "javaRepoHead": git_head(java_root),
            "cloudRepoHead": git_head(cloud_root),
        },
        "sourceRuntimeIndex": {
            "path": str(runtime_index_path),
            "exists": runtime_index_path.exists(),
            "status": runtime_status,
            "javaRuntimeBlocker": java_blocker,
        },
        "handoffGate": handoff_gate,
        "mainbaseHandoff": {
            "bundleName": handoff.get("bundleName"),
            "handoffRoot": str(handoff_root),
            "handoffManifest": str(handoff_manifest_path),
            "handoffTar": str(handoff_tar_path),
            "handoffTarSha256File": str(handoff_tar_sha_path),
            "handoffTarSha256": tar_actual_sha,
            "tarSha256Expected": tar_expected_sha,
            "tarSha256Matches": tar_ok,
            "bundleChecksumStatus": bundle_checksum,
            "missingRequiredRoles": missing_roles,
            "mainbaseGate": mainbase_gate,
            "files": files,
            "tarMemberCount": len(tar_list),
            "tarMembersPreview": tar_list[:40],
        },
        "cloudPathMapping": {
            "extractRoot": "/mnt/soundlayer-artifacts",
            "handoffRoot": "/mnt/soundlayer-artifacts/week12_soundlayer_blueprint_v1_cloud_handoff",
            "env": {
                "SOUNDLAYER_HANDOFF_ROOT": "/mnt/soundlayer-artifacts/week12_soundlayer_blueprint_v1_cloud_handoff",
                "SOUNDLAYER_BLUEPRINT_MANIFEST": "/mnt/soundlayer-artifacts/week12_soundlayer_blueprint_v1_cloud_handoff/manifests/week12_blueprint_v1_manifest.json",
                "SOUNDLAYER_EVENT_TIMELINE_JSONL": "/mnt/soundlayer-artifacts/week12_soundlayer_blueprint_v1_cloud_handoff/manifests/week12_event_timeline.jsonl",
                "SOUNDLAYER_EVENT_TIMELINE_CSV": "/mnt/soundlayer-artifacts/week12_soundlayer_blueprint_v1_cloud_handoff/manifests/week12_event_timeline.csv",
                "SOUNDLAYER_CONTACT_SHEET": "/mnt/soundlayer-artifacts/week12_soundlayer_blueprint_v1_cloud_handoff/visuals/week12_event_timeline_contact_sheet.png",
                "SOUNDLAYER_BLUEPRINT_SCHEMA": "/mnt/soundlayer-artifacts/week12_soundlayer_blueprint_v1_cloud_handoff/schema/soundlayer_blueprint_v1.schema.json",
            },
        },
        "doesNotClaim": [
            "Java runtime HTTP success",
            "audio generation",
            "live Grafana import",
            "production Kubernetes storage",
            "k6 load test",
        ],
        "nextAction": "Use the handoff-aware artifact index as the Cloud input for worker/dashboard wiring; Java runtime remains a separate blocker.",
    }

    overview_md = "\n".join(
        [
            "## Week12 SoundLayer handoff readiness",
            "",
            f"- Artifact status: `{artifact_status}`",
            f"- Mainbase repo head: `{git_head(mainbase_root)}`",
            f"- Handoff source head: `{handoff.get('sourceHead')}`",
            f"- Runtime status: `{runtime_status}`",
            f"- Java blocker: `{java_blocker_type}`",
            f"- Tar sha256: `{tar_actual_sha[:12]}`",
        ]
    )

    handoff_md = "\n".join(
        [
            "## Handoff bundle",
            "",
            f"- Bundle name: `{handoff.get('bundleName')}`",
            f"- Bundle checksum status: `{bundle_checksum.get('status')}`",
            f"- Tar sha256 matches: `{tar_ok}`",
            f"- Required roles present: `{not missing_roles}`",
            f"- Missing roles: `{missing_roles}`",
        ]
    )

    counts_md = "\n".join(
        [
            "## Blueprint counts",
            "",
            f"- Blueprint count: `{mainbase_gate.get('blueprintCount')}`",
            f"- Event count: `{mainbase_gate.get('eventCount')}`",
            f"- Timeline JSONL rows: `{mainbase_gate.get('timelineJsonlRows')}`",
            f"- Timeline CSV rows: `{mainbase_gate.get('timelineCsvRows')}`",
        ]
    )

    path_md = "\n".join(
        [
            "## Handoff mount mapping",
            "",
            "- `SOUNDLAYER_HANDOFF_ROOT=/mnt/soundlayer-artifacts/week12_soundlayer_blueprint_v1_cloud_handoff`",
            "- `SOUNDLAYER_BLUEPRINT_MANIFEST=${SOUNDLAYER_HANDOFF_ROOT}/manifests/week12_blueprint_v1_manifest.json`",
            "- `SOUNDLAYER_EVENT_TIMELINE_JSONL=${SOUNDLAYER_HANDOFF_ROOT}/manifests/week12_event_timeline.jsonl`",
            "- `SOUNDLAYER_CONTACT_SHEET=${SOUNDLAYER_HANDOFF_ROOT}/visuals/week12_event_timeline_contact_sheet.png`",
        ]
    )

    blocker_md = "\n".join(
        [
            "## Java runtime blocker",
            "",
            f"- Status: `{java_blocker.get('status')}`",
            f"- Type: `{java_blocker_type}`",
            f"- Evidence log: `{java_blocker.get('evidence_log')}`",
            "",
            "This dashboard does not claim Java HTTP runtime success.",
        ]
    )

    dashboard_status = (
        "DASHBOARD_READY_WITH_MAINBASE_HANDOFF_AND_JAVA_RUNTIME_BLOCKED"
        if all_handoff_ready
        else "FAIL"
    )

    dashboard_json = {
        "uid": "week12-soundlayer-artifact-dashboard",
        "title": "Week12 SoundLayer Handoff Readiness",
        "tags": ["week12", "soundlayer", "handoff", "blueprint", "runtime-blocker"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 2,
        "refresh": "",
        "time": {"from": "now-24h", "to": "now"},
        "panels": [
            panel(1, "Handoff Readiness Overview", overview_md, 0, 0, 12, 6),
            panel(2, "Handoff Bundle Gate", handoff_md, 12, 0, 12, 6),
            panel(3, "Blueprint Counts", counts_md, 0, 6, 12, 6),
            panel(4, "Handoff Mount Mapping", path_md, 12, 6, 12, 6),
            panel(5, "Java Runtime Blocker", blocker_md, 0, 12, 24, 6),
        ],
        "templating": {"list": []},
        "annotations": {"list": []},
    }

    dashboard_index = {
        "schemaVersion": "week12.dashboard-ready-index.v2",
        "generatedAt": now,
        "status": dashboard_status,
        "sourceArtifactPathIndex": str(artifact_index_path),
        "sourceRuntimeIndex": str(runtime_index_path),
        "sourceHandoffManifest": str(handoff_manifest_path),
        "sourceHandoffTar": str(handoff_tar_path),
        "grafanaDashboardJson": str(dashboard_json_path),
        "requiredReady": handoff_gate,
        "summary": {
            "mainbaseRepoHead": git_head(mainbase_root),
            "mainbaseHandoffSourceHead": handoff.get("sourceHead"),
            "runtimeStatus": runtime_status,
            "javaRuntimeBlockerType": java_blocker_type,
            "blueprintCount": mainbase_gate.get("blueprintCount"),
            "eventCount": mainbase_gate.get("eventCount"),
            "timelineJsonlRows": mainbase_gate.get("timelineJsonlRows"),
            "timelineCsvRows": mainbase_gate.get("timelineCsvRows"),
            "handoffRoot": "/mnt/soundlayer-artifacts/week12_soundlayer_blueprint_v1_cloud_handoff",
            "handoffTarSha256": tar_actual_sha,
            "bundleChecksumStatus": bundle_checksum.get("status"),
        },
        "doesNotClaim": [
            "dashboard imported into a live Grafana server",
            "Prometheus datasource wired",
            "Java runtime HTTP success",
            "production Kubernetes storage",
            "k6 load test",
        ],
        "nextAction": "Commit the handoff-aware Cloud indexes, then decide whether to fix Java runtime with a PostgreSQL-backed test profile.",
    }

    artifact_index_path.write_text(json.dumps(handoff_artifact_index, indent=2, ensure_ascii=False), encoding="utf-8")
    dashboard_index_path.write_text(json.dumps(dashboard_index, indent=2, ensure_ascii=False), encoding="utf-8")
    dashboard_json_path.write_text(json.dumps(dashboard_json, indent=2, ensure_ascii=False), encoding="utf-8")

    log_path = log_dir / f"week12_handoff_aware_cloud_index_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path.write_text(
        "\n".join(
            [
                f"artifact_status={artifact_status}",
                f"dashboard_status={dashboard_status}",
                f"mainbase_repo_head={git_head(mainbase_root)}",
                f"handoff_source_head={handoff.get('sourceHead')}",
                f"runtime_status={runtime_status}",
                f"java_blocker={java_blocker_type}",
                f"tar_sha256_matches={tar_ok}",
                f"bundle_checksum_status={bundle_checksum.get('status')}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"artifact_status={artifact_status}")
    print(f"dashboard_status={dashboard_status}")
    print(f"mainbase_repo_head={git_head(mainbase_root)}")
    print(f"handoff_source_head={handoff.get('sourceHead')}")
    print(f"runtime_status={runtime_status}")
    print(f"java_blocker={java_blocker_type}")
    print(f"tar_sha256_matches={tar_ok}")
    print(f"bundle_checksum_status={bundle_checksum.get('status')}")
    print(f"artifact_index={artifact_index_path}")
    print(f"dashboard_index={dashboard_index_path}")
    print(f"dashboard_json={dashboard_json_path}")
    print(f"log_path={log_path}")

    return 0 if all_handoff_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())