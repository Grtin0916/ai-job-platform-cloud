#!/usr/bin/env python3
"""Cross-repository Ranker delivery contract validation."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head(root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "--short", "HEAD"], text=True
    ).strip()


def verify_delivery(delivery_root: Path) -> tuple[int, int, list[str]]:
    entries = []
    for line in (delivery_root / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        entries.append((digest, relative))
    failures = [
        relative
        for digest, relative in entries
        if not (delivery_root / relative).is_file()
        or sha256_file(delivery_root / relative) != digest
    ]
    return len(entries), len(entries) - len(failures), failures


def build_snapshot(
    mainbase_root: Path,
    java_root: Path,
    cloud_root: Path,
    mainbase_delivery: Path,
    java_version_report: Path,
    java_events: Path,
) -> dict[str, Any]:
    delivery_report = load_json(mainbase_root / mainbase_delivery)
    delivery_root = mainbase_root / delivery_report["bundleRelativePath"]
    manifest = load_json(delivery_root / "manifest.json")
    java_report = load_json(java_root / java_version_report)
    versions = java_report["versions"]
    if len(versions) != 1:
        raise ValueError("expected exactly one Java ranker version")
    java_version = versions[0]
    events = [
        json.loads(line)
        for line in (java_root / java_events).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    checksums, verified, failures = verify_delivery(delivery_root)
    digest_match = manifest["bundleDigest"] == java_version["bundleDigest"]
    promotion_match = manifest["promotionStatus"] == java_version["promotionStatus"]
    if not digest_match or not promotion_match:
        raise ValueError("Mainbase and Java ranker contracts disagree")
    labels_path = mainbase_root / "annotations/preference_labels_20260727.csv"
    with labels_path.open(encoding="utf-8", newline="") as stream:
        review_rows = sum(1 for _ in csv.DictReader(stream))
    snapshot = {
        "schemaVersion": "ranker-contract-snapshot/v1",
        "repositories": {
            "mainbaseGitHead": git_head(mainbase_root),
            "javaGitHead": git_head(java_root),
            "cloudGitHead": git_head(cloud_root),
        },
        "ranker": {
            "rankerName": manifest["rankerName"],
            "rankerVersion": manifest["rankerVersion"],
            "bundleDigest": manifest["bundleDigest"],
            "promotionStatus": manifest["promotionStatus"],
            "modelPresent": manifest["modelPresent"],
            "oofAvailable": manifest["oofAvailable"],
            "recommendationCount": manifest["recommendationCount"],
            "reviewRows": review_rows,
            "reviewSubmittedCount": manifest["reviewSubmittedCount"],
            "humanReviewCompleted": manifest["humanReviewCompleted"],
            "finalSelectedMutationCount": manifest["finalSelectedMutationCount"],
            "blockedReason": manifest["blockedReason"],
        },
        "registry": {
            "versionCount": java_report["versionCount"],
            "registryImportResult": "REGISTERED_AND_REUSED"
            if {event["eventType"] for event in events}
            >= {"RANKER_REGISTERED", "RANKER_IMPORT_REUSED"}
            else "INCOMPLETE",
            "versionConflictCount": sum(
                event.get("eventType") == "RANKER_VERSION_CONFLICT" for event in events
            ),
            "eventCount": len(events),
        },
        "artifactIntegrity": {
            "ready": checksums > 0 and checksums == verified,
            "checksumCount": checksums,
            "checksumVerifiedCount": verified,
            "checksumFailures": failures,
            "crossRepositoryDigestMatch": digest_match,
            "crossRepositoryPromotionMatch": promotion_match,
        },
        "claimBoundary": {
            "proxyOnly": True,
            "humanGateRequired": True,
            "autoFinalForbidden": True,
            "productionWorkflowVerified": False,
        },
    }
    validate_snapshot(snapshot)
    return snapshot


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    ranker = snapshot["ranker"]
    if ranker["promotionStatus"] == "DATA_BLOCKED" and (
        ranker["modelPresent"]
        or ranker["oofAvailable"]
        or ranker["recommendationCount"] != 0
    ):
        raise ValueError("DATA_BLOCKED contains learned outputs")
    if ranker["finalSelectedMutationCount"] != 0:
        raise ValueError("Ranker changed final selection")
    if not snapshot["artifactIntegrity"]["ready"]:
        raise ValueError("Ranker delivery checksum validation failed")


def write_snapshot_csv(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ranker = snapshot["ranker"]
    row = {
        **snapshot["repositories"],
        **ranker,
        "registryImportResult": snapshot["registry"]["registryImportResult"],
        "versionConflictCount": snapshot["registry"]["versionConflictCount"],
        "artifactIntegrityReady": snapshot["artifactIntegrity"]["ready"],
    }
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row), lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)
