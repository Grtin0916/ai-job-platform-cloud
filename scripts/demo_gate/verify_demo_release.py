#!/usr/bin/env python3
"""Verify the release directory and deterministic ZIP member/digest contract."""

from __future__ import annotations

import argparse
import json
import wave
import zipfile
from pathlib import Path, PurePosixPath

from common import contains_host_path, dump_json, load_json, sha256_file


def verify(release_root: Path, zip_path: Path) -> dict:
    manifest = load_json(release_root / "manifest.json")
    checksums = {}
    for line in (release_root / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        checksums[name] = digest
    directory_members = sorted(
        str(path.relative_to(release_root)).replace("\\", "/")
        for path in release_root.rglob("*")
        if path.is_file()
    )
    checksum_failures = [
        name
        for name, expected in checksums.items()
        if not (release_root / name).is_file() or sha256_file(release_root / name) != expected
    ]
    unsafe = [
        name
        for name in directory_members
        if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
    ]
    with zipfile.ZipFile(zip_path) as archive:
        zip_members = sorted(archive.namelist())
        bad_crc = archive.testzip()
        zip_payloads_match = all(
            archive.read(name) == (release_root / name).read_bytes() for name in zip_members
        )
    jobs = load_json(release_root / "data/jobs.json")
    cards = jobs["caseResultCards"]
    audio_members = [name for name in directory_members if name.startswith("audio/")]
    unreadable_audio = []
    for name in audio_members:
        try:
            with wave.open(str(release_root / name), "rb") as audio:
                if (
                    audio.getnchannels() < 1
                    or audio.getframerate() < 1
                    or audio.getnframes() < 1
                ):
                    unreadable_audio.append(name)
        except (wave.Error, EOFError):
            unreadable_audio.append(name)
    host_leak = contains_host_path(
        {
            "cards": cards,
            "artifacts": load_json(release_root / "data/artifacts.json"),
            "provenance": load_json(release_root / "provenance.json"),
        }
    )
    report = {
        "verified": (
            not checksum_failures
            and not unsafe
            and bad_crc is None
            and zip_members == manifest["archiveMembers"] == directory_members
            and zip_payloads_match
            and len(cards) == 12
            and len(audio_members) == 10
            and not unreadable_audio
            and sum(card["publishDecision"] != "PROVISIONAL_SELECTED" for card in cards) == 2
            and sum(card["finalSelected"] for card in cards) == 0
            and not host_leak
        ),
        "zipTestResult": bad_crc,
        "zipMemberCount": len(zip_members),
        "directoryMemberCount": len(directory_members),
        "memberSetMatches": zip_members == manifest["archiveMembers"] == directory_members,
        "zipPayloadsMatchDirectory": zip_payloads_match,
        "checksumFailureCount": len(checksum_failures),
        "unsafePathCount": len(unsafe),
        "hostPathLeakCount": int(host_leak),
        "caseRecordCount": len(cards),
        "playableProvisionalCount": len(audio_members),
        "unreadableAudioCount": len(unreadable_audio),
        "blockedOrRejectedCount": sum(
            card["publishDecision"] != "PROVISIONAL_SELECTED" for card in cards
        ),
        "finalSelectedCount": sum(card["finalSelected"] for card in cards),
        "releaseStatus": manifest["releaseStatus"],
        "zipSha256": sha256_file(zip_path),
        "checksumsSelfEntryExcluded": manifest["checksumsSelfEntryExcluded"],
    }
    return report


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
