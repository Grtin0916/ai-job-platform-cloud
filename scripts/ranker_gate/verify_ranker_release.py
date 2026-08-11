#!/usr/bin/env python3
"""Verify W21 Ranker release CRC, members, hashes, audio and claim boundary."""

from __future__ import annotations

import argparse
import json
import wave
import zipfile
from pathlib import Path, PurePosixPath

from ranker_contract import dump_json, load_json, sha256_file


def verify(release_root: Path, zip_path: Path) -> dict:
    manifest = load_json(release_root / "manifest.json")
    boundary = load_json(release_root / "claim-boundary.json")
    checksums = {}
    for line in (release_root / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        checksums[relative] = digest
    directory_members = sorted(
        path.relative_to(release_root).as_posix()
        for path in release_root.rglob("*") if path.is_file()
    )
    checksum_failures = [
        name for name, digest in checksums.items()
        if not (release_root / name).is_file() or sha256_file(release_root / name) != digest
    ]
    unsafe = [
        name for name in directory_members
        if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
    ]
    with zipfile.ZipFile(zip_path) as archive:
        zip_members = sorted(archive.namelist())
        crc_failure = archive.testzip()
        payload_match = all(archive.read(name) == (release_root / name).read_bytes() for name in zip_members)
    audio_members = [name for name in directory_members if name.startswith("audio/")]
    unreadable = []
    for name in audio_members:
        try:
            with wave.open(str(release_root / name), "rb") as stream:
                if stream.getnchannels() < 1 or stream.getframerate() < 1 or stream.getnframes() < 1:
                    unreadable.append(name)
        except (wave.Error, EOFError):
            unreadable.append(name)
    boundary_valid = (
        boundary["promotionStatus"] == "DATA_BLOCKED"
        and not boundary["modelAvailable"]
        and not boundary["oofAvailable"]
        and boundary["recommendationCount"] == 0
        and boundary["finalSelectedCount"] == 0
        and boundary["audioExamplesAreW20Provisional"]
        and not boundary["audioExamplesAreRankerRecommendations"]
    )
    verified = (
        not checksum_failures and not unsafe and crc_failure is None and payload_match
        and zip_members == manifest["archiveMembers"] == directory_members
        and len(audio_members) == 4 and not unreadable and boundary_valid
        and manifest["releaseDecision"] == "HOLD_HUMAN_REVIEW"
        and manifest["finalSelectedCount"] == 0
    )
    return {
        "schemaVersion": "w21-ranker-release-verify/v1",
        "verified": verified,
        "releaseDecision": manifest["releaseDecision"],
        "zipTestResult": crc_failure,
        "memberSetMatches": zip_members == manifest["archiveMembers"] == directory_members,
        "zipPayloadsMatchDirectory": payload_match,
        "checksumFailureCount": len(checksum_failures),
        "unsafePathCount": len(unsafe),
        "playableAudioCount": len(audio_members),
        "unreadableAudioCount": len(unreadable),
        "claimBoundaryValid": boundary_valid,
        "finalSelectedCount": manifest["finalSelectedCount"],
        "zipSha256": sha256_file(zip_path),
        "signedAttestationVerified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.release_root, args.zip)
    dump_json(args.out, report)
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report["verified"] else 1)


if __name__ == "__main__":
    main()
