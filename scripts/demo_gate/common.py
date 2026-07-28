#!/usr/bin/env python3
"""Shared helpers for the durable demo release gate."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(path: Path | str, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit(root: Path | str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def contained_file(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ValueError(f"path must be repository-relative: {relative!r}")
    real_root = root.resolve(strict=True)
    candidate = root.joinpath(relative)
    if candidate.is_symlink():
        raise ValueError(f"symbolic link is not accepted: {relative}")
    real = candidate.resolve(strict=True)
    if real_root not in (real, *real.parents) or not real.is_file():
        raise ValueError(f"path escapes allowed root: {relative}")
    return real


def digest_without_prefix(value: str) -> str:
    digest = value.removeprefix("sha256:")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError(f"invalid SHA-256: {value}")
    return digest


def contains_host_path(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False)
    return any(marker in text for marker in ("/home/", "~/", "\\\\", "C:\\"))
