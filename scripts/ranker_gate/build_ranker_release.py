#!/usr/bin/env python3
"""Build a deterministic standalone HOLD Ranker release with four real WAV files."""

from __future__ import annotations

import argparse
import html
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from ranker_contract import dump_json, load_json, sha256_file

FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)


def write_zip(root: Path, target: Path, members: list[str]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in members:
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (root / name).read_bytes())


def build(
    snapshot_path: Path,
    java_report_path: Path,
    gate_path: Path,
    failures_path: Path,
    events_path: Path,
    metrics_path: Path,
    rules_path: Path,
    dashboard_path: Path,
    w20_release_root: Path,
    release_root: Path,
    zip_path: Path,
) -> dict:
    snapshot = load_json(snapshot_path)
    gate = load_json(gate_path)
    if gate["baselineDecision"] != "HOLD_HUMAN_REVIEW":
        raise ValueError("only the verified HOLD release can be packaged")
    if release_root.exists():
        shutil.rmtree(release_root)
    for name in ("audio", "data", "observability"):
        (release_root / name).mkdir(parents=True, exist_ok=True)
    audio_sources = sorted((w20_release_root / "audio").glob("*.wav"))[:4]
    if len(audio_sources) != 4:
        raise ValueError("four real W20 WAV artifacts are required")
    audio_records = []
    for source in audio_sources:
        target = release_root / "audio" / source.name
        shutil.copy2(source, target)
        audio_records.append({
            "relativePath": f"audio/{source.name}",
            "sha256": sha256_file(target),
            "claim": "W20_PROVISIONAL_EXAMPLE_NOT_RANKER_RECOMMENDATION",
        })
    copies = {
        "data/ranker-contract.json": snapshot_path,
        "data/java-version-report.json": java_report_path,
        "data/release-gate.json": gate_path,
        "data/gate-failures.json": failures_path,
        "data/ranker-events.jsonl": events_path,
        "observability/metrics.prom": metrics_path,
        "observability/rules.yml": rules_path,
        "observability/dashboard.json": dashboard_path,
    }
    for relative, source in copies.items():
        shutil.copy2(source, release_root / relative)
    boundary = {
        "schemaVersion": "w21-ranker-claim-boundary/v1",
        "promotionStatus": "DATA_BLOCKED",
        "modelAvailable": False,
        "oofAvailable": False,
        "recommendationCount": 0,
        "humanReviewCompleted": False,
        "finalSelectedCount": 0,
        "audioExamplesAreW20Provisional": True,
        "audioExamplesAreRankerRecommendations": False,
        "audioExamplesProveHumanPreference": False,
        "productionWorkflowVerified": False,
        "nextRequiredAction": "Complete 48 blind preference reviews",
    }
    provenance = {
        "schemaVersion": "w21-ranker-release-provenance/v1",
        "repositories": snapshot["repositories"],
        "bundleDigest": snapshot["ranker"]["bundleDigest"],
        "releaseBuildKind": "local-reproducible-zip",
        "githubActionsBuilt": False,
        "signedAttestationVerified": False,
        "audioRecords": audio_records,
    }
    dump_json(release_root / "claim-boundary.json", boundary)
    dump_json(release_root / "provenance.json", provenance)
    ranker = snapshot["ranker"]
    audio_html = "\n".join(
        f'<article><h2>{html.escape(Path(item["relativePath"]).stem)}</h2>'
        f'<audio controls preload="metadata" src="{html.escape(item["relativePath"])}"></audio></article>'
        for item in audio_records
    )
    (release_root / "index.html").write_text(
        """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>W21 Ranker HOLD Release</title></head><body>
<h1>Missingness-aware Ranker Observatory</h1>
"""
        + f"<p>Ranker Version: {html.escape(ranker['rankerVersion'])}</p>\n"
        + "<p>Promotion Status: DATA_BLOCKED</p>\n"
        + "<p>Model / OOF: No / No · Recommendations: 0</p>\n"
        + f"<p>Human Reviews: {ranker['reviewSubmittedCount']} / {ranker['reviewRows']} · Final Selected: 0</p>\n"
        + "<p>System Status: Operational · Release Decision: HOLD_HUMAN_REVIEW</p>\n"
        + "<p>Next Required Step: Complete blind preference review.</p>\n"
        + "<aside><strong>Claim boundary:</strong> These four WAV files are real W20 provisional/repair examples. "
        + "They are not Ranker v1 recommendations and do not prove human preference.</aside>\n"
        + audio_html
        + "\n</body></html>\n",
        encoding="utf-8",
    )
    payload_members = sorted(
        path.relative_to(release_root).as_posix()
        for path in release_root.rglob("*") if path.is_file()
    )
    payload_hashes = {name: sha256_file(release_root / name) for name in payload_members}
    archive_members = sorted(payload_members + ["manifest.json", "checksums.sha256"])
    manifest = {
        "schemaVersion": "w21-ranker-hold-release/v1",
        "releaseDecision": "HOLD_HUMAN_REVIEW",
        "systemStatus": "OPERATIONAL",
        "promotionStatus": "DATA_BLOCKED",
        "playableAudioCount": 4,
        "recommendationCount": 0,
        "finalSelectedCount": 0,
        "payloadMembers": payload_members,
        "archiveMembers": archive_members,
        "payloadSha256": payload_hashes,
        "checksumsSelfEntryExcluded": True,
        "claimBoundary": boundary,
    }
    dump_json(release_root / "manifest.json", manifest)
    checksums = {**payload_hashes, "manifest.json": sha256_file(release_root / "manifest.json")}
    (release_root / "checksums.sha256").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items())),
        encoding="utf-8",
    )
    write_zip(release_root, zip_path, archive_members)
    with tempfile.TemporaryDirectory() as temporary:
        second = Path(temporary) / "release.zip"
        write_zip(release_root, second, archive_members)
        reproducible = sha256_file(zip_path) == sha256_file(second)
    return {
        "releaseDecision": "HOLD_HUMAN_REVIEW",
        "memberCount": len(archive_members),
        "playableAudioCount": 4,
        "zipSha256": sha256_file(zip_path),
        "reproducibleZipVerified": reproducible,
        "finalSelectedCount": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("snapshot", "java-report", "gate", "failures", "events", "metrics", "rules", "dashboard", "w20-release-root", "release-root", "zip"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.snapshot, args.java_report, args.gate, args.failures, args.events, args.metrics, args.rules, args.dashboard, args.w20_release_root, args.release_root, args.zip)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
