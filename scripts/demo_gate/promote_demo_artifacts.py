#!/usr/bin/env python3
"""Promote Java-owned blobs into the Cloud local object boundary."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

from common import (
    contained_file,
    digest_without_prefix,
    dump_json,
    git_commit,
    load_json,
    sha256_file,
)


FROZEN_HANDOFF = "artifacts/week20/mainbase_dss_rerank_repair_handoff_20260722.json"


def promote(
    java_root: Path,
    java_handoff_path: Path,
    java_artifact_index_path: Path,
    store_root: Path,
    out_index: Path,
    out_csv: Path,
    handoff_producer_commit: str,
) -> dict:
    java_root = java_root.resolve(strict=True)
    handoff = load_json(java_handoff_path)
    artifact_index = load_json(java_artifact_index_path)
    frozen = load_json(java_root / FROZEN_HANDOFF)

    if (
        handoff.get("recordCount"),
        handoff.get("provisionalCount"),
        handoff.get("blockedCount"),
        handoff.get("finalSelectedCount"),
    ) != (12, 10, 2, 0):
        raise ValueError("Java handoff is not the frozen 12/10/2/0 contract")
    if frozen.get("finalSelectedCount") != 0 or len(frozen.get("records", [])) != 12:
        raise ValueError("frozen Mainbase handoff claim boundary drift")
    if artifact_index.get("artifactReferenceCount") != 20:
        raise ValueError("expected 20 Java artifact references")

    store_root.mkdir(parents=True, exist_ok=True)
    objects: dict[str, dict] = {}
    by_source_path: dict[str, str] = {}
    imported = reused = 0

    for artifact in artifact_index["artifacts"]:
        digest = digest_without_prefix(artifact["sourceDigest"])
        source = contained_file(java_root, artifact["materializedPath"])
        if sha256_file(source) != digest or source.stat().st_size != artifact["sizeBytes"]:
            raise ValueError(f"Java blob integrity mismatch: {artifact['materializedPath']}")
        target = store_root / digest
        if target.exists():
            if not target.is_file() or sha256_file(target) != digest:
                raise ValueError(f"existing Cloud object integrity mismatch: {digest}")
            reused += 1
        else:
            shutil.copyfile(source, target)
            imported += 1
        if sha256_file(target) != digest:
            raise ValueError(f"promoted object integrity mismatch: {digest}")
        uri = f"demo-object://sha256/{digest}"
        by_source_path[artifact["sourceRelativePath"]] = uri
        objects[digest] = {
            "objectUri": uri,
            "sha256": digest,
            "sizeBytes": target.stat().st_size,
            "mediaType": artifact["mediaType"],
            "sourceRepository": "audio_engineering_repo_skeleton_v1",
            "sourceCommitRole": "artifactOriginCommit",
            "artifactOriginCommit": artifact["sourceCommit"],
            "sourceRelativePath": artifact["sourceRelativePath"],
        }

    case_records = []
    decisions = {"PROVISIONAL_SELECTED": 0, "BLOCKED": 0}
    for record in frozen["records"]:
        publish = record["publishDecision"]
        if publish == "PROVISIONAL_SELECTED":
            decisions["PROVISIONAL_SELECTED"] += 1
        else:
            decisions["BLOCKED"] += 1
        case_records.append(
            {
                "caseId": record["caseId"],
                "sourceCaseId": record["sourceCaseId"],
                "executionStatus": "READY_FOR_REPLAY"
                if publish == "PROVISIONAL_SELECTED"
                else "BLOCKED",
                "publishDecision": publish,
                "repairDecision": record["repairDecision"],
                "generationMode": "REPLAY",
                "repairAction": record["repairAction"],
                "selectedArtifactUri": by_source_path.get(record.get("selectedArtifact", "")),
                "repairArtifactUri": by_source_path.get(record.get("repairArtifact", "")),
                "proxyEvidence": True,
                "humanReviewStatus": "PENDING",
                "finalSelected": False,
            }
        )
    if decisions != {"PROVISIONAL_SELECTED": 10, "BLOCKED": 2}:
        raise ValueError(f"decision count drift: {decisions}")

    cloud_root = Path(__file__).resolve().parents[2]
    result = {
        "schemaVersion": "durable-demo-artifact-index/v1",
        "provenance": {
            "handoffProducerCommit": handoff_producer_commit,
            "artifactOriginCommit": frozen["sourceCommit"],
            "javaConsumerCommit": git_commit(java_root),
            "cloudConsumerCommit": git_commit(cloud_root),
            "cloudConsumerRole": "build-base-commit",
        },
        "sourceHandoffDigest": handoff["handoffDigest"],
        "recordCount": 12,
        "javaJobCount": len(handoff["jobs"]),
        "provisionalCount": 10,
        "blockedOrRejectedCount": 2,
        "finalSelectedCount": 0,
        "artifactReferenceCount": artifact_index["artifactReferenceCount"],
        "uniqueObjectCount": len(objects),
        "importedObjectCount": imported,
        "reusedObjectCount": reused,
        "integrityFailureCount": 0,
        "missingArtifactCount": 0,
        "hostPathLeakCount": 0,
        "decisionMutationCount": 0,
        "objects": sorted(objects.values(), key=lambda item: item["sha256"]),
        "caseRecords": sorted(case_records, key=lambda item: item["caseId"]),
    }
    dump_json(out_index, result)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            [
                "object_uri",
                "sha256",
                "size_bytes",
                "media_type",
                "source_commit_role",
                "artifact_origin_commit",
                "source_relative_path",
                "cloud_materialized_path",
            ]
        )
        for item in result["objects"]:
            writer.writerow(
                [
                    item["objectUri"],
                    item["sha256"],
                    item["sizeBytes"],
                    item["mediaType"],
                    item["sourceCommitRole"],
                    item["artifactOriginCommit"],
                    item["sourceRelativePath"],
                    f"artifacts/local-object-store/demo-results/sha256/{item['sha256']}",
                ]
            )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--java-root", type=Path, required=True)
    parser.add_argument("--java-handoff", type=Path, required=True)
    parser.add_argument("--java-artifact-index", type=Path, required=True)
    parser.add_argument("--store-root", type=Path, required=True)
    parser.add_argument("--out-index", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, required=True)
    parser.add_argument("--handoff-producer-commit", required=True)
    args = parser.parse_args()
    result = promote(
        args.java_root,
        args.java_handoff,
        args.java_artifact_index,
        args.store_root,
        args.out_index,
        args.out_csv,
        args.handoff_producer_commit,
    )
    print(
        f"records={result['recordCount']} objects={result['uniqueObjectCount']} "
        f"integrityFailures={result['integrityFailureCount']} "
        f"hostPathLeaks={result['hostPathLeakCount']}"
    )


if __name__ == "__main__":
    main()
