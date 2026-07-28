#!/usr/bin/env python3
"""SQLite durable ledger with idempotent imports and fenced writes."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA_VERSION = 1
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS schema_meta (
  version INTEGER PRIMARY KEY,
  applied_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS imports (
  import_digest TEXT PRIMARY KEY,
  source_handoff_digest TEXT NOT NULL,
  imported_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
  java_job_id TEXT PRIMARY KEY,
  cloud_job_key TEXT UNIQUE NOT NULL,
  request_fingerprint TEXT NOT NULL,
  import_digest TEXT NOT NULL REFERENCES imports(import_digest),
  case_id TEXT NOT NULL,
  mode TEXT NOT NULL,
  execution_status TEXT NOT NULL,
  publish_decision TEXT NOT NULL,
  final_selected INTEGER NOT NULL CHECK(final_selected = 0),
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
  attempt_key TEXT PRIMARY KEY,
  java_job_id TEXT NOT NULL REFERENCES jobs(java_job_id),
  attempt_number INTEGER NOT NULL,
  status TEXT NOT NULL,
  exit_code INTEGER,
  result_digest TEXT,
  payload_json TEXT NOT NULL,
  UNIQUE(java_job_id, attempt_number)
);
CREATE TABLE IF NOT EXISTS artifacts (
  object_uri TEXT PRIMARY KEY,
  sha256 TEXT UNIQUE NOT NULL,
  size_bytes INTEGER NOT NULL,
  media_type TEXT NOT NULL,
  artifact_origin_commit TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  event_type TEXT NOT NULL,
  resource_key TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS leases (
  resource_key TEXT PRIMARY KEY,
  holder_id TEXT NOT NULL,
  fencing_token INTEGER NOT NULL,
  acquired_at REAL NOT NULL,
  renewed_at REAL NOT NULL,
  expires_at REAL NOT NULL,
  version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS releases (
  release_key TEXT PRIMARY KEY,
  java_job_id TEXT,
  case_id TEXT,
  status TEXT NOT NULL,
  publish_decision TEXT NOT NULL,
  artifact_uri TEXT,
  fencing_token INTEGER,
  created_at REAL NOT NULL
);
"""


class ContractConflict(RuntimeError):
    pass


class LeaseConflict(RuntimeError):
    pass


class StaleFence(RuntimeError):
    pass


class CloudJobLedger:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self.connection.execute(
            "INSERT OR IGNORE INTO schema_meta(version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, time.time()),
        )

    def close(self) -> None:
        self.connection.close()

    @contextmanager
    def immediate(self) -> Iterator[sqlite3.Connection]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def event(self, event_type: str, resource_key: str, payload: dict) -> None:
        self.connection.execute(
            "INSERT INTO events(event_type, resource_key, payload_json, created_at) VALUES (?, ?, ?, ?)",
            (event_type, resource_key, json.dumps(payload, sort_keys=True), time.time()),
        )

    def acquire_lease(
        self, resource_key: str, holder_id: str, ttl_seconds: float, now: float | None = None
    ) -> int:
        now = time.time() if now is None else now
        with self.immediate() as connection:
            current = connection.execute(
                "SELECT * FROM leases WHERE resource_key = ?", (resource_key,)
            ).fetchone()
            if current is not None and current["expires_at"] > now:
                if current["holder_id"] == holder_id:
                    connection.execute(
                        "UPDATE leases SET renewed_at=?, expires_at=?, version=version+1 "
                        "WHERE resource_key=?",
                        (now, now + ttl_seconds, resource_key),
                    )
                    return int(current["fencing_token"])
                raise LeaseConflict(
                    f"{resource_key} held by {current['holder_id']} until {current['expires_at']}"
                )
            token = 1 if current is None else int(current["fencing_token"]) + 1
            if current is None:
                connection.execute(
                    "INSERT INTO leases VALUES (?, ?, ?, ?, ?, ?, 1)",
                    (resource_key, holder_id, token, now, now, now + ttl_seconds),
                )
            else:
                connection.execute(
                    "UPDATE leases SET holder_id=?, fencing_token=?, acquired_at=?, renewed_at=?, "
                    "expires_at=?, version=version+1 WHERE resource_key=?",
                    (holder_id, token, now, now, now + ttl_seconds, resource_key),
                )
            return token

    def finalize(
        self,
        resource_key: str,
        holder_id: str,
        token: int,
        release_key: str,
        java_job_id: str,
        now: float | None = None,
    ) -> None:
        now = time.time() if now is None else now
        with self.immediate() as connection:
            lease = connection.execute(
                "SELECT * FROM leases WHERE resource_key=?", (resource_key,)
            ).fetchone()
            if (
                lease is None
                or lease["holder_id"] != holder_id
                or lease["fencing_token"] != token
            ):
                raise StaleFence(f"stale token {token} for {resource_key}")
            cursor = connection.execute(
                "INSERT OR IGNORE INTO releases("
                "release_key, java_job_id, case_id, status, publish_decision, "
                "artifact_uri, fencing_token, created_at) VALUES (?, ?, NULL, ?, ?, NULL, ?, ?)",
                (release_key, java_job_id, "FINALIZED_EXECUTION", "PROVISIONAL_SELECTED", token, now),
            )
            if cursor.rowcount == 0:
                raise ContractConflict(f"duplicate release: {release_key}")
        self.event(
            "LEASE_FINALIZED",
            resource_key,
            {"holderId": holder_id, "fencingToken": token, "releaseKey": release_key},
        )

    def counts(self) -> dict[str, int]:
        names = ("jobs", "attempts", "artifacts", "events", "leases", "releases", "imports")
        return {
            name: int(self.connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
            for name in names
        }

    def rows(self, table: str) -> list[dict]:
        allowed = {"jobs", "attempts", "artifacts", "events", "leases", "releases", "imports"}
        if table not in allowed:
            raise ValueError(table)
        return [dict(row) for row in self.connection.execute(f"SELECT * FROM {table}")]
