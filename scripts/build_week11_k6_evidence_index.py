#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any


OUT = Path("loadtest/reports/week11_k6_evidence_index.json")


def sh(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:
        return f"unknown: {exc}"


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": str(exc), "_path": str(path)}


def file_info(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "modified_at_epoch": int(path.stat().st_mtime),
    }


def glob_files(patterns: list[str]) -> list[Path]:
    out: list[Path] = []
    for pat in patterns:
        out.extend(sorted(Path(".").glob(pat)))
    return sorted({p for p in out if p.is_file()})


def classify_report(path: Path) -> str:
    name = path.name.lower()
    text = ""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()[:20000]
    except Exception:
        pass

    if "artifacturi" in text or "evalsummaryuri" in text or "qualitygatestatus" in text or "artifact" in name or "consumer" in name:
        return "eval_artifact_link_consumer"
    if "slo" in text or "threshold" in text or "http_req_duration" in text or "http_req_failed" in text:
        return "query_slo_smoke"
    if "k6" in name:
        return "k6_related"
    return "unknown"


def extract_k6_metrics(obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict):
        return {}

    metrics = obj.get("metrics")
    if not isinstance(metrics, dict):
        return {}

    picked: dict[str, Any] = {}
    for key in ("http_req_duration", "http_req_failed", "http_reqs", "checks", "iterations"):
        if key in metrics:
            picked[key] = metrics[key]
    return picked


def main() -> None:
    report_paths = glob_files([
        "loadtest/reports/*week11*.json",
        "loadtest/reports/*k6*.json",
        "artifacts/logs/*week11*k6*.log",
        "artifacts/logs/*k6*.log",
    ])

    report_items = []
    role_counts: dict[str, int] = {}

    for p in report_paths:
        role = classify_report(p)
        role_counts[role] = role_counts.get(role, 0) + 1
        item = {
            "path": str(p),
            "role": role,
            "file": file_info(p),
        }
        if p.suffix == ".json":
            parsed = read_json(p)
            item["k6_metrics_subset"] = extract_k6_metrics(parsed)
            if isinstance(parsed, dict):
                item["top_level_keys"] = sorted(parsed.keys())[:40]
        report_items.append(item)

    expected_fields = ["artifactUri", "evalSummaryUri", "qualityGateStatus"]
    all_text = ""
    for p in report_paths:
        try:
            all_text += "\n" + p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass

    field_presence = {
        field: field in all_text
        for field in expected_fields
    }

    payload = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "index_name": "week11_k6_evidence_index",
        "purpose": "Cloud Week11 evidence index: merge k6/SLO smoke evidence and eval artifact-link consumer evidence into one machine-readable report.",
        "boundary": "V0 local Cloud evidence only. Not a production SLO, not Alertmanager/on-call proof, not real cloud capacity evidence.",
        "repo": {
            "name": "ai-job-platform-cloud",
            "role": "Cloud: k6/SLO/consumer evidence index",
            "commit": sh(["git", "rev-parse", "--short", "HEAD"]),
            "tracked_git_status": sh(["git", "status", "-sb", "--untracked-files=no"]),
            "full_git_status_at_build": sh(["git", "status", "-sb"]),
        },
        "cross_repo_inputs": {
            "mainbase_evidence_commit_from_user": "1defdc4",
            "java_evidence_contract_commit_from_user": "c6558c9",
            "java_evidence_fields": expected_fields,
        },
        "evidence_roles": {
            "counts": role_counts,
            "has_query_slo_smoke": role_counts.get("query_slo_smoke", 0) > 0,
            "has_eval_artifact_link_consumer": role_counts.get("eval_artifact_link_consumer", 0) > 0,
        },
        "consumer_field_presence": field_presence,
        "reports": report_items,
        "quality_gate": {
            "pass": (
                role_counts.get("query_slo_smoke", 0) > 0
                and role_counts.get("eval_artifact_link_consumer", 0) > 0
                and all(field_presence.values())
            ),
            "rule": "PASS if Cloud has at least one SLO/query k6 evidence, at least one artifact-link consumer evidence, and all expected Java evidence fields appear in reports/logs.",
        },
        "next_recommended_edge": {
            "repo": "ai-job-platform-cloud",
            "action": "Use this index as the Cloud-side evidence root for README/weekly summary without rerunning long k6.",
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "out": str(OUT),
        "cloud_commit": payload["repo"]["commit"],
        "role_counts": role_counts,
        "consumer_field_presence": field_presence,
        "quality_gate_pass": payload["quality_gate"]["pass"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()