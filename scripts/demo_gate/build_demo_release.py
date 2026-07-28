#!/usr/bin/env python3
"""Build a deterministic 12-case demo release from promoted Cloud objects."""

from __future__ import annotations

import argparse
import html
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from cloud_job_ledger import CloudJobLedger
from common import dump_json, load_json, sha256_bytes, sha256_file


FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)


def write_zip(root: Path, target: Path, members: list[str]) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in members:
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (root / name).read_bytes())


def build(
    artifact_index_path: Path,
    store_root: Path,
    db: Path,
    events_path: Path,
    k6_summary_path: Path,
    metrics_path: Path,
    rules_path: Path,
    dashboard_path: Path,
    observability_report_path: Path,
    release_root: Path,
    zip_path: Path,
) -> dict:
    artifact_index = load_json(artifact_index_path)
    observability = load_json(observability_report_path)
    ledger = CloudJobLedger(db)
    actual_jobs = [
        {
            key: row[key]
            for key in (
                "java_job_id",
                "case_id",
                "mode",
                "execution_status",
                "publish_decision",
                "final_selected",
            )
        }
        for row in ledger.rows("jobs")
    ]
    ledger.close()

    if release_root.exists():
        shutil.rmtree(release_root)
    for directory in ("audio", "data", "observability"):
        (release_root / directory).mkdir(parents=True, exist_ok=True)

    objects = {item["objectUri"]: item for item in artifact_index["objects"]}
    cards = []
    audio_count = 0
    for case in artifact_index["caseRecords"]:
        selected_uri = (
            case["selectedArtifactUri"]
            if case["publishDecision"] == "PROVISIONAL_SELECTED"
            else None
        )
        audio_relative = None
        sha256 = None
        if selected_uri:
            item = objects[selected_uri]
            source = store_root / item["sha256"]
            audio_relative = f"audio/{case['caseId']}.wav"
            shutil.copyfile(source, release_root / audio_relative)
            sha256 = item["sha256"]
            audio_count += 1
        cards.append(
            {
                **case,
                "artifactUri": selected_uri,
                "audioPath": audio_relative,
                "sha256": sha256,
                "artifactOriginCommit": artifact_index["provenance"]["artifactOriginCommit"],
                "handoffProducerCommit": artifact_index["provenance"]["handoffProducerCommit"],
                "javaConsumerCommit": artifact_index["provenance"]["javaConsumerCommit"],
                "cloudConsumerCommit": artifact_index["provenance"]["cloudConsumerCommit"],
                "proxyEvidence": True,
                "humanReviewStatus": "PENDING",
                "finalSelected": False,
            }
        )

    dump_json(
        release_root / "data/jobs.json",
        {"caseResultCards": cards, "actualJavaJobs": actual_jobs},
    )
    dump_json(release_root / "data/artifacts.json", artifact_index)
    shutil.copyfile(events_path, release_root / "data/events.jsonl")
    if k6_summary_path.is_file():
        shutil.copyfile(k6_summary_path, release_root / "data/k6-summary.json")
    else:
        dump_json(
            release_root / "data/k6-summary.json",
            {"executed": False, "runtimeBlockedReason": "k6 summary was not produced"},
        )
    shutil.copyfile(metrics_path, release_root / "observability/metrics.prom")
    shutil.copyfile(rules_path, release_root / "observability/rules.yml")
    shutil.copyfile(dashboard_path, release_root / "observability/dashboard.json")

    provenance = {
        **artifact_index["provenance"],
        "sourceHandoffDigest": artifact_index["sourceHandoffDigest"],
        "releaseBuildKind": "local-reproducible-zip",
        "slsaCompliant": False,
        "signedAttestation": False,
        "githubActionsBuilt": False,
    }
    boundaries = {
        "artifactReady": True,
        "ledgerReady": True,
        "leaseRecoveryReady": observability["leaseRecoveryVerified"],
        "k6Executed": observability["k6Executed"],
        "k6ThresholdPassed": observability["k6ThresholdPassed"],
        "humanGateReady": False,
        "finalSelectionReady": False,
        "productionWorkflowVerified": False,
        "distributedExactlyOnce": False,
    }
    dump_json(release_root / "provenance.json", provenance)
    dump_json(release_root / "claim-boundary.json", boundaries)

    sections = []
    for card in cards:
        audio = (
            f'<audio controls preload="metadata" src="{html.escape(card["audioPath"])}"></audio>'
            if card["audioPath"]
            else "<p>No audio published: release decision is blocked.</p>"
        )
        sections.append(
            "<article>"
            f"<h2>{html.escape(card['caseId'])}</h2>"
            f"<p>{html.escape(card['publishDecision'])} · human review pending · finalSelected=false</p>"
            f"{audio}</article>"
        )
    (release_root / "index.html").write_text(
        """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>W20 Durable Demo Release</title></head><body>
<h1>Director-guided Video-to-Audio — W20 Release Gate</h1>
<p>10 provisional replay artifacts, 2 blocked cases, 0 final selections.</p>
"""
        + "\n".join(sections)
        + "\n</body></html>\n",
        encoding="utf-8",
    )

    payload_members = sorted(
        str(path.relative_to(release_root)).replace("\\", "/")
        for path in release_root.rglob("*")
        if path.is_file()
    )
    payload_hashes = {name: sha256_file(release_root / name) for name in payload_members}
    archive_members = sorted(payload_members + ["manifest.json", "checksums.sha256"])
    manifest = {
        "schemaVersion": "w20-durable-demo-release/v1",
        "releaseStatus": "GATE_PASSED"
        if observability["k6ThresholdPassed"]
        else "GATE_FAILED",
        "caseRecordCount": len(cards),
        "playableProvisionalCount": audio_count,
        "blockedOrRejectedCount": sum(
            item["publishDecision"] != "PROVISIONAL_SELECTED" for item in cards
        ),
        "finalSelectedCount": 0,
        "payloadMembers": payload_members,
        "archiveMembers": archive_members,
        "payloadSha256": payload_hashes,
        "checksumsSelfEntryExcluded": True,
        "claimBoundary": boundaries,
        "provenance": provenance,
    }
    dump_json(release_root / "manifest.json", manifest)
    checksums = dict(payload_hashes)
    checksums["manifest.json"] = sha256_file(release_root / "manifest.json")
    (release_root / "checksums.sha256").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items())),
        encoding="utf-8",
    )

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    write_zip(release_root, zip_path, archive_members)
    with tempfile.TemporaryDirectory() as temporary:
        second = Path(temporary) / "release.zip"
        write_zip(release_root, second, archive_members)
        reproducible = sha256_file(zip_path) == sha256_file(second)
    result = {
        "releaseStatus": manifest["releaseStatus"],
        "caseRecordCount": len(cards),
        "playableProvisionalCount": audio_count,
        "blockedOrRejectedCount": manifest["blockedOrRejectedCount"],
        "finalSelectedCount": 0,
        "zipSha256": sha256_file(zip_path),
        "reproducibleZipVerified": reproducible,
    }
    print(json.dumps(result, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in (
        "artifact-index",
        "store-root",
        "db",
        "events",
        "k6-summary",
        "metrics",
        "rules",
        "dashboard",
        "observability-report",
        "release-root",
        "zip",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    build(
        args.artifact_index,
        args.store_root,
        args.db,
        args.events,
        args.k6_summary,
        args.metrics,
        args.rules,
        args.dashboard,
        args.observability_report,
        args.release_root,
        args.zip,
    )


if __name__ == "__main__":
    main()
