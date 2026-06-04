#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_short_head(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()


def git_remote(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "remote", "get-url", "origin"],
        text=True,
    ).strip()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        obj = json.loads(line)
        if not isinstance(obj, dict):
            raise ValueError(f"{path}:{line_no} is not a JSON object")
        obj["_sourceLine"] = line_no
        rows.append(obj)
    return rows


def main() -> int:
    mainbase = Path.home() / "work" / "audio_engineering_repo_skeleton_v1"
    cloud = Path.home() / "work" / "ai-job-platform-cloud"

    audition_manifest_rel = Path("artifacts/manifests/week12_procedural_audio_audition_manifest_v0.json")
    audition_metrics_jsonl_rel = Path("artifacts/manifests/week12_procedural_audio_audition_metrics_v0.jsonl")
    audition_metrics_csv_rel = Path("artifacts/manifests/week12_procedural_audio_audition_metrics_v0.csv")

    audition_manifest_path = mainbase / audition_manifest_rel
    metrics_jsonl_path = mainbase / audition_metrics_jsonl_rel
    metrics_csv_path = mainbase / audition_metrics_csv_rel

    required_mainbase_files = [
        audition_manifest_path,
        metrics_jsonl_path,
        metrics_csv_path,
    ]

    missing = [str(p) for p in required_mainbase_files if not p.exists()]
    if missing:
        raise SystemExit("MISSING_MAINBASE_AUDITION_FILES=" + json.dumps(missing, ensure_ascii=False))

    audition_manifest = load_json(audition_manifest_path)
    metrics_rows = load_jsonl(metrics_jsonl_path)

    outputs = audition_manifest.get("outputs") or {}
    html_rel = Path(outputs.get("auditionHtml", ""))
    svg_rel = Path(outputs.get("waveformContactSheetSvg", ""))

    html_path = mainbase / html_rel
    svg_path = mainbase / svg_rel

    artifact_paths = [
        html_path,
        svg_path,
        metrics_jsonl_path,
        metrics_csv_path,
    ]

    missing_artifacts = [str(p) for p in artifact_paths if not p.exists()]

    checks = {
        "mainbaseAuditionManifestPass": audition_manifest.get("status") == "PASS",
        "candidateCountMatchesMetrics": audition_manifest.get("candidateCount") == len(metrics_rows),
        "qaRecordCountMatchesMetrics": audition_manifest.get("qaRecordCount") == len(metrics_rows),
        "allFormatOk": audition_manifest.get("allFormatOk") is True,
        "allDurationMatchesExpected": audition_manifest.get("allDurationMatchesExpected") is True,
        "allRequireHumanAudition": audition_manifest.get("allRequireHumanAudition") is True,
        "semanticFidelityNotClaimed": audition_manifest.get("semanticFidelityClaimedAny") is False,
        "mixReadyNotClaimed": audition_manifest.get("mixReadyClaimedAny") is False,
        "htmlExists": html_path.exists(),
        "waveformContactSheetExists": svg_path.exists(),
        "metricsJsonlExists": metrics_jsonl_path.exists(),
        "metricsCsvExists": metrics_csv_path.exists(),
        "noMissingArtifacts": not missing_artifacts,
    }

    status = "PASS" if all(checks.values()) else "BLOCKED"
    blockers = [k for k, ok in checks.items() if not ok]

    index = {
        "schemaVersion": "week12.audio-audition-artifact-index.v0",
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": status,
        "mainbaseAuditionEvidence": {
            "repo": git_remote(mainbase),
            "commit": git_short_head(mainbase),
            "auditionManifestPath": str(audition_manifest_rel),
            "auditionManifestSha256": sha256_file(audition_manifest_path),
            "auditionHtmlPath": str(html_rel),
            "auditionHtmlSha256": sha256_file(html_path) if html_path.exists() else None,
            "waveformContactSheetSvgPath": str(svg_rel),
            "waveformContactSheetSvgSha256": sha256_file(svg_path) if svg_path.exists() else None,
            "metricsJsonlPath": str(audition_metrics_jsonl_rel),
            "metricsJsonlSha256": sha256_file(metrics_jsonl_path),
            "metricsCsvPath": str(audition_metrics_csv_rel),
            "metricsCsvSha256": sha256_file(metrics_csv_path),
        },
        "cloudEvidence": {
            "repo": git_remote(cloud),
            "commitBeforeIndex": git_short_head(cloud),
            "indexPath": "loadtest/reports/week12_audio_audition_artifact_index.json",
        },
        "auditionSummary": {
            "candidateCount": audition_manifest.get("candidateCount"),
            "qaRecordCount": audition_manifest.get("qaRecordCount"),
            "allFormatOk": audition_manifest.get("allFormatOk"),
            "allDurationMatchesExpected": audition_manifest.get("allDurationMatchesExpected"),
            "allRequireHumanAudition": audition_manifest.get("allRequireHumanAudition"),
            "semanticFidelityClaimedAny": audition_manifest.get("semanticFidelityClaimedAny"),
            "mixReadyClaimedAny": audition_manifest.get("mixReadyClaimedAny"),
            "aggregateMetrics": audition_manifest.get("aggregateMetrics"),
            "importantVisual": str(svg_rel),
            "importantAuditionHtml": str(html_rel),
        },
        "consumedMetricExamples": [
            {
                "candidateId": row.get("candidateId"),
                "layer": row.get("layer"),
                "eventLabel": row.get("eventLabel"),
                "durationSec": (row.get("metrics") or {}).get("durationSec"),
                "rmsDbfs": (row.get("metrics") or {}).get("rmsDbfs"),
                "peakDbfs": (row.get("metrics") or {}).get("peakDbfs"),
                "formatOk": row.get("formatOk"),
                "durationMatchesExpected": row.get("durationMatchesExpected"),
                "candidateUri": row.get("candidateUri"),
            }
            for row in metrics_rows[:3]
        ],
        "checks": checks,
        "blockers": blockers,
        "doesNotClaim": [
            "semantic audio quality",
            "human audition has passed",
            "final mix readiness",
            "text-to-audio model inference",
            "production asset storage",
            "real cloud object storage upload"
        ],
    }

    out = cloud / "loadtest/reports/week12_audio_audition_artifact_index.json"
    out.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(index, indent=2, ensure_ascii=False))

    return 0 if status == "PASS" else 4


if __name__ == "__main__":
    raise SystemExit(main())