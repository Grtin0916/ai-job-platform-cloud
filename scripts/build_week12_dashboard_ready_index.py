#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def panel(panel_id: int, title: str, markdown: str, x: int, y: int, w: int, h: int) -> dict[str, Any]:
    return {
        "id": panel_id,
        "type": "text",
        "title": title,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "options": {
            "mode": "markdown",
            "content": markdown,
        },
    }


def short_hash(value: str | None) -> str:
    if not value:
        return "missing"
    return value[:12]


def main() -> int:
    cloud_root = Path.home() / "work" / "grt_work" / "ai-job-platform-cloud"

    artifact_index_path = cloud_root / "loadtest/reports/week12_blueprint_artifact_path_index.json"
    runtime_index_path = cloud_root / "loadtest/reports/week12_asset_blueprint_runtime_index.json"

    out_report = cloud_root / "loadtest/reports/week12_dashboard_ready_index.json"
    out_dashboard = cloud_root / "observability/grafana/dashboards/week12_soundlayer_artifact_dashboard.json"
    log_dir = cloud_root / "artifacts/logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_dashboard.parent.mkdir(parents=True, exist_ok=True)

    artifact_index = read_json(artifact_index_path)
    runtime_index = read_json(runtime_index_path)

    artifact_gate = artifact_index.get("mainbaseArtifactGate", {})
    artifact_catalog = artifact_index.get("artifactCatalog", {})
    path_mapping = artifact_index.get("cloudPathMapping", {})
    runtime_status = runtime_index.get("status")
    java_blocker = runtime_index.get("java", {}).get("runtimeBlocker", {})

    manifest = artifact_catalog.get("manifest", {})
    timeline_jsonl = artifact_catalog.get("timeline_jsonl", {})
    timeline_csv = artifact_catalog.get("timeline_csv", {})
    contact_sheet = artifact_catalog.get("contact_sheet_png", {})

    required_ready = {
        "artifact_index_exists": artifact_index_path.exists(),
        "runtime_index_exists": runtime_index_path.exists(),
        "mainbase_gate_pass": artifact_gate.get("status") == "PASS",
        "blueprint_count_is_5": artifact_gate.get("blueprintCount") == 5,
        "event_count_is_10": artifact_gate.get("eventCount") == 10,
        "timeline_jsonl_rows_is_10": artifact_gate.get("timelineJsonlRows") == 10,
        "timeline_csv_rows_is_10": artifact_gate.get("timelineCsvRows") == 10,
        "manifest_hash_present": bool(manifest.get("sha256")),
        "timeline_jsonl_hash_present": bool(timeline_jsonl.get("sha256")),
        "contact_sheet_exists": contact_sheet.get("exists") is True,
        "runtime_blocker_recorded": runtime_status == "BLOCKED_BY_JAVA_RUNTIME"
        and java_blocker.get("type") == "FLYWAY_H2_POSTGRESQL_TYPE_MISMATCH",
        "k8s_mount_path_present": bool(path_mapping.get("k8sSuggestedMountPath")),
    }

    dashboard_status = (
        "DASHBOARD_READY_WITH_JAVA_RUNTIME_BLOCKED"
        if all(required_ready.values())
        else "FAIL"
    )

    env = path_mapping.get("env", {})
    k8s_mount = path_mapping.get("k8sSuggestedMountPath", "missing")

    overview_md = "\n".join(
        [
            f"## Week12 SoundLayer Blueprint V1",
            "",
            f"- Dashboard status: `{dashboard_status}`",
            f"- Mainbase artifact gate: `{artifact_gate.get('status')}`",
            f"- Runtime status: `{runtime_status}`",
            f"- Java blocker: `{java_blocker.get('type')}`",
            f"- Does not claim: Java HTTP runtime success, audio generation, production Kubernetes volume, k6 load test.",
        ]
    )

    artifact_md = "\n".join(
        [
            "## Artifact counts",
            "",
            f"- Blueprint count: `{artifact_gate.get('blueprintCount')}`",
            f"- Event count: `{artifact_gate.get('eventCount')}`",
            f"- Timeline JSONL rows: `{artifact_gate.get('timelineJsonlRows')}`",
            f"- Timeline CSV rows: `{artifact_gate.get('timelineCsvRows')}`",
            f"- Contact sheet exists: `{contact_sheet.get('exists')}`",
        ]
    )

    hash_md = "\n".join(
        [
            "## Artifact fingerprints",
            "",
            f"- Manifest sha256: `{short_hash(manifest.get('sha256'))}`",
            f"- Timeline JSONL sha256: `{short_hash(timeline_jsonl.get('sha256'))}`",
            f"- Timeline CSV sha256: `{short_hash(timeline_csv.get('sha256'))}`",
            f"- Contact sheet sha256: `{short_hash(contact_sheet.get('sha256'))}`",
        ]
    )

    path_md = "\n".join(
        [
            "## Cloud path mapping",
            "",
            f"- Suggested k8s mount: `{k8s_mount}`",
            f"- `SOUNDLAYER_BLUEPRINT_MANIFEST={env.get('SOUNDLAYER_BLUEPRINT_MANIFEST', 'missing')}`",
            f"- `SOUNDLAYER_EVENT_TIMELINE_JSONL={env.get('SOUNDLAYER_EVENT_TIMELINE_JSONL', 'missing')}`",
            f"- `SOUNDLAYER_EVENT_TIMELINE_CSV={env.get('SOUNDLAYER_EVENT_TIMELINE_CSV', 'missing')}`",
            f"- `SOUNDLAYER_CONTACT_SHEET={env.get('SOUNDLAYER_CONTACT_SHEET', 'missing')}`",
        ]
    )

    blocker_md = "\n".join(
        [
            "## Java runtime blocker",
            "",
            f"- Status: `{java_blocker.get('status')}`",
            f"- Type: `{java_blocker.get('type')}`",
            f"- Evidence log: `{java_blocker.get('evidence_log')}`",
            "",
            "Next gate: fix Java test/runtime profile or switch DB-backed runtime verification to PostgreSQL/Testcontainers.",
        ]
    )

    generated_at = datetime.now(timezone.utc).isoformat()

    dashboard_json = {
        "uid": "week12-soundlayer-artifact-dashboard",
        "title": "Week12 SoundLayer Artifact Readiness",
        "tags": ["week12", "soundlayer", "artifact", "blueprint", "runtime-blocker"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "",
        "time": {"from": "now-24h", "to": "now"},
        "panels": [
            panel(1, "Readiness Overview", overview_md, 0, 0, 12, 6),
            panel(2, "Blueprint Artifact Counts", artifact_md, 12, 0, 12, 6),
            panel(3, "Artifact Fingerprints", hash_md, 0, 6, 12, 7),
            panel(4, "Cloud Path Mapping", path_md, 12, 6, 12, 7),
            panel(5, "Java Runtime Blocker", blocker_md, 0, 13, 24, 6),
        ],
        "templating": {"list": []},
        "annotations": {"list": []},
    }

    dashboard_index = {
        "schemaVersion": "week12.dashboard-ready-index.v1",
        "generatedAt": generated_at,
        "status": dashboard_status,
        "sourceArtifactPathIndex": str(artifact_index_path),
        "sourceRuntimeIndex": str(runtime_index_path),
        "grafanaDashboardJson": str(out_dashboard),
        "requiredReady": required_ready,
        "summary": {
            "mainbaseArtifactGate": artifact_gate.get("status"),
            "runtimeStatus": runtime_status,
            "javaRuntimeBlockerType": java_blocker.get("type"),
            "blueprintCount": artifact_gate.get("blueprintCount"),
            "eventCount": artifact_gate.get("eventCount"),
            "timelineJsonlRows": artifact_gate.get("timelineJsonlRows"),
            "timelineCsvRows": artifact_gate.get("timelineCsvRows"),
            "k8sSuggestedMountPath": k8s_mount,
            "manifestSha256": manifest.get("sha256"),
            "timelineJsonlSha256": timeline_jsonl.get("sha256"),
            "contactSheetExists": contact_sheet.get("exists"),
        },
        "doesNotClaim": [
            "dashboard imported into a live Grafana server",
            "Prometheus datasource wired",
            "Java runtime HTTP success",
            "production Kubernetes storage",
            "k6 load test",
        ],
        "nextAction": "Import or provision this dashboard JSON after Grafana is available; meanwhile use the dashboard-ready index as a machine-readable Cloud readiness gate.",
    }

    out_dashboard.write_text(json.dumps(dashboard_json, indent=2, ensure_ascii=False), encoding="utf-8")
    out_report.write_text(json.dumps(dashboard_index, indent=2, ensure_ascii=False), encoding="utf-8")

    log_path = log_dir / f"week12_dashboard_ready_index_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path.write_text(
        "\n".join(
            [
                f"status={dashboard_status}",
                f"out_report={out_report}",
                f"out_dashboard={out_dashboard}",
                f"mainbase_gate={artifact_gate.get('status')}",
                f"runtime_status={runtime_status}",
                f"java_blocker={java_blocker.get('type')}",
                f"k8s_mount={k8s_mount}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"status={dashboard_status}")
    print(f"out_report={out_report}")
    print(f"out_dashboard={out_dashboard}")
    print(f"log_path={log_path}")
    print(f"mainbase_gate={artifact_gate.get('status')}")
    print(f"runtime_status={runtime_status}")
    print(f"java_blocker={java_blocker.get('type')}")
    print(f"k8s_mount={k8s_mount}")

    return 0 if dashboard_status == "DASHBOARD_READY_WITH_JAVA_RUNTIME_BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())