#!/usr/bin/env python3
"""
Build Week13 candidate-level platform drilldown table.

Inputs:
- Mainbase mix global placement table CSV.
- Cloud ready candidate worker input table CSV.
- Cloud local audio worker smoke table CSV.
- Cloud Java API platform readiness gate JSON.

Outputs:
- candidate-level drilldown CSV
- candidate-level drilldown JSON
- drilldown summary JSON

Boundary:
- dashboard-ready drilldown data only
- does not claim live Grafana import
- does not claim semantic audio quality
- does not claim human audition pass
- does not claim final mix readiness
- does not claim production Kubernetes Job or production object storage
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ID_KEYS = [
    "candidateId",
    "candidate_id",
    "id",
    "audioCandidateId",
    "audio_candidate_id",
]

MODE_KEYS = [
    "assetTimeMode",
    "asset_time_mode",
    "timeMode",
    "time_mode",
]

SUCCESS_KEYS = [
    "workerSuccess",
    "success",
    "status",
    "workerStatus",
    "worker_status",
]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required json: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(f"missing required csv: {path}")
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def pick_key(fields: list[str], candidates: list[str]) -> str | None:
    exact = {f: f for f in fields}
    lower = {f.lower(): f for f in fields}
    for c in candidates:
        if c in exact:
            return exact[c]
        if c.lower() in lower:
            return lower[c.lower()]
    return None


def normalize_id(row: dict[str, str], id_key: str | None, fallback: int) -> str:
    if id_key and row.get(id_key):
        return str(row[id_key]).strip()
    return f"row_{fallback:02d}"


def index_rows(rows: list[dict[str, str]], id_key: str | None) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for i, row in enumerate(rows, start=1):
        cid = normalize_id(row, id_key, i)
        out[cid] = row
    return out


def prefixed(row: dict[str, str] | None, prefix: str) -> dict[str, str]:
    if not row:
        return {}
    return {f"{prefix}.{k}": v for k, v in row.items()}


def success_value(row: dict[str, str] | None, success_key: str | None) -> str:
    if not row or not success_key:
        return ""
    return str(row.get(success_key, "")).strip()


def is_success_like(value: str) -> bool:
    v = value.strip().lower()
    return v in {"pass", "passed", "success", "succeeded", "true", "ok", "1", "done"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--mainbase-placement-table",
        type=Path,
        required=True,
    )
    ap.add_argument(
        "--cloud-worker-input-table",
        type=Path,
        default=Path("loadtest/reports/week13_ready_candidate_worker_input_table.csv"),
    )
    ap.add_argument(
        "--cloud-worker-smoke-table",
        type=Path,
        default=Path("loadtest/reports/week13_local_audio_worker_smoke_table.csv"),
    )
    ap.add_argument(
        "--cloud-gate",
        type=Path,
        default=Path("loadtest/reports/week13_java_api_platform_readiness_gate.json"),
    )
    ap.add_argument(
        "--csv-out",
        type=Path,
        default=Path("loadtest/reports/week13_candidate_bank_platform_drilldown_table.csv"),
    )
    ap.add_argument(
        "--json-out",
        type=Path,
        default=Path("loadtest/reports/week13_candidate_bank_platform_drilldown_table.json"),
    )
    ap.add_argument(
        "--summary-out",
        type=Path,
        default=Path("loadtest/reports/week13_candidate_bank_platform_drilldown_summary.json"),
    )
    args = ap.parse_args()

    placement_fields, placement_rows = read_csv(args.mainbase_placement_table)
    input_fields, input_rows = read_csv(args.cloud_worker_input_table)
    smoke_fields, smoke_rows = read_csv(args.cloud_worker_smoke_table)
    gate = read_json(args.cloud_gate)

    placement_id_key = pick_key(placement_fields, ID_KEYS)
    input_id_key = pick_key(input_fields, ID_KEYS)
    smoke_id_key = pick_key(smoke_fields, ID_KEYS)

    if not placement_id_key:
        raise SystemExit(f"cannot find candidate id column in placement table fields={placement_fields}")
    if not input_id_key:
        raise SystemExit(f"cannot find candidate id column in worker input table fields={input_fields}")
    if not smoke_id_key:
        raise SystemExit(f"cannot find candidate id column in worker smoke table fields={smoke_fields}")

    placement_mode_key = pick_key(placement_fields, MODE_KEYS)
    input_mode_key = pick_key(input_fields, MODE_KEYS)
    smoke_success_key = pick_key(smoke_fields, SUCCESS_KEYS)

    placement_by_id = index_rows(placement_rows, placement_id_key)
    input_by_id = index_rows(input_rows, input_id_key)
    smoke_by_id = index_rows(smoke_rows, smoke_id_key)

    candidate_ids = sorted(set(placement_by_id) | set(input_by_id) | set(smoke_by_id))

    drilldown_rows: list[dict[str, Any]] = []
    blockers: list[str] = []

    for cid in candidate_ids:
        p = placement_by_id.get(cid)
        wi = input_by_id.get(cid)
        ws = smoke_by_id.get(cid)

        smoke_success_raw = success_value(ws, smoke_success_key)
        smoke_success = is_success_like(smoke_success_raw)

        placement_mode = ""
        if p and placement_mode_key:
            placement_mode = p.get(placement_mode_key, "")
        input_mode = ""
        if wi and input_mode_key:
            input_mode = wi.get(input_mode_key, "")

        row_ready = bool(p) and bool(wi) and bool(ws) and smoke_success

        if not p:
            blockers.append(f"{cid}:missing_placement_row")
        if not wi:
            blockers.append(f"{cid}:missing_worker_input_row")
        if not ws:
            blockers.append(f"{cid}:missing_worker_smoke_row")
        if ws and not smoke_success:
            blockers.append(f"{cid}:worker_smoke_not_success:{smoke_success_raw}")

        base = {
            "candidateId": cid,
            "rowReady": row_ready,
            "placementPresent": bool(p),
            "workerInputPresent": bool(wi),
            "workerSmokePresent": bool(ws),
            "placementAssetTimeMode": placement_mode,
            "workerInputAssetTimeMode": input_mode,
            "workerSmokeSuccessRaw": smoke_success_raw,
            "workerSmokeSuccess": smoke_success,
        }
        base.update(prefixed(p, "placement"))
        base.update(prefixed(wi, "workerInput"))
        base.update(prefixed(ws, "workerSmoke"))
        drilldown_rows.append(base)

    ready_count = sum(1 for r in drilldown_rows if r["rowReady"])
    full_clip_count = sum(
        1 for r in drilldown_rows
        if str(r.get("placementAssetTimeMode", "")).strip() == "full_clip"
        or str(r.get("workerInputAssetTimeMode", "")).strip() == "full_clip"
    )
    event_local_count = sum(
        1 for r in drilldown_rows
        if str(r.get("placementAssetTimeMode", "")).strip() == "event_local"
        or str(r.get("workerInputAssetTimeMode", "")).strip() == "event_local"
    )

    hard_checks = {
        "gateStatusPass": gate.get("status") == "PASS",
        "rowCountIsTen": len(drilldown_rows) == 10,
        "readyCountIsTen": ready_count == 10,
        "noBlockers": len(blockers) == 0,
        "allPlacementRowsPresent": all(r["placementPresent"] for r in drilldown_rows),
        "allWorkerInputRowsPresent": all(r["workerInputPresent"] for r in drilldown_rows),
        "allWorkerSmokeRowsPresent": all(r["workerSmokePresent"] for r in drilldown_rows),
        "allWorkerSmokeSuccess": all(r["workerSmokeSuccess"] for r in drilldown_rows),
    }

    status = "PASS" if all(hard_checks.values()) else "FAIL"

    summary = {
        "schemaVersion": "week13.cloud_candidate_bank_platform_drilldown_summary.v1",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "scope": "candidate-level-dashboard-drilldown-data",
        "sourcePlacementTable": str(args.mainbase_placement_table),
        "sourceWorkerInputTable": str(args.cloud_worker_input_table),
        "sourceWorkerSmokeTable": str(args.cloud_worker_smoke_table),
        "sourceGate": str(args.cloud_gate),
        "csvOut": str(args.csv_out),
        "jsonOut": str(args.json_out),
        "counts": {
            "candidateCount": len(drilldown_rows),
            "readyCount": ready_count,
            "fullClipLikeCount": full_clip_count,
            "eventLocalLikeCount": event_local_count,
        },
        "detectedColumns": {
            "placementIdKey": placement_id_key,
            "workerInputIdKey": input_id_key,
            "workerSmokeIdKey": smoke_id_key,
            "placementModeKey": placement_mode_key,
            "workerInputModeKey": input_mode_key,
            "workerSmokeSuccessKey": smoke_success_key,
        },
        "hardChecks": hard_checks,
        "blockers": [] if status == "PASS" else blockers,
        "boundary": [
            "does_not_claim_semantic_audio_quality",
            "does_not_claim_human_audition_pass",
            "does_not_claim_final_mix_readiness",
            "does_not_claim_live_grafana_import",
            "does_not_claim_production_kubernetes_job",
            "does_not_claim_s3_minio_csi_or_cloud_object_storage",
        ],
    }

    args.csv_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)

    fieldnames: list[str] = []
    for row in drilldown_rows:
        for k in row.keys():
            if k not in fieldnames:
                fieldnames.append(k)

    with args.csv_out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(drilldown_rows)

    args.json_out.write_text(json.dumps(drilldown_rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.summary_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": status,
        "csvOut": str(args.csv_out),
        "jsonOut": str(args.json_out),
        "summaryOut": str(args.summary_out),
        "counts": summary["counts"],
        "detectedColumns": summary["detectedColumns"],
        "failedChecks": [k for k, v in hard_checks.items() if not v],
        "blockers": summary["blockers"],
    }, indent=2, ensure_ascii=False))

    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())