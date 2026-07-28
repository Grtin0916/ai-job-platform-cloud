#!/usr/bin/env python3
"""Focused tests for the W20 durable demo release gate."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts/demo_gate"
sys.path.insert(0, str(SCRIPTS))

from cloud_job_ledger import CloudJobLedger, ContractConflict, LeaseConflict, StaleFence
from import_java_demo_jobs import import_records
from promote_demo_artifacts import promote
from verify_demo_artifacts import verify


WORKSPACE = ROOT.parent
JAVA = WORKSPACE / "media-task-platform-java"


class ArtifactPromotionTest(unittest.TestCase):
    def test_real_java_blobs_promote_without_host_path_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            index = root / "index.json"
            result = promote(
                JAVA,
                JAVA / "artifacts/manifests/w20_demo_job_cloud_handoff_20260723.json",
                JAVA / "artifacts/manifests/w20_demo_artifact_index_20260723.json",
                root / "objects",
                index,
                root / "mapping.csv",
                "fd1422d",
            )
            self.assertEqual(12, result["recordCount"])
            self.assertEqual(20, result["uniqueObjectCount"])
            self.assertEqual(10, result["provisionalCount"])
            self.assertEqual(2, result["blockedOrRejectedCount"])
            self.assertTrue(verify(index, root / "objects")["verified"])


def fixture_contract() -> tuple[dict, dict, dict]:
    job = {
        "jobId": "java-1",
        "requestFingerprint": "a" * 64,
        "caseId": "case-1",
        "mode": "REPLAY",
        "executionStatus": "SUCCEEDED",
        "publishDecision": "PROVISIONAL_SELECTED",
        "attempts": [
            {
                "attemptId": "attempt-001",
                "attemptNumber": 1,
                "status": "SUCCEEDED",
                "exitCode": 0,
                "resultDigest": "b" * 64,
            }
        ],
    }
    handoff = {"handoffDigest": "c" * 64, "jobs": [job]}
    report = {"recordCount": 12, "finalSelectedCount": 0}
    cases = [
        {
            "caseId": f"case-{index}",
            "executionStatus": "READY_FOR_REPLAY" if index < 10 else "BLOCKED",
            "publishDecision": "PROVISIONAL_SELECTED" if index < 10 else "REPAIR_REJECTED",
            "selectedArtifactUri": "demo-object://sha256/" + "d" * 64 if index < 10 else None,
        }
        for index in range(12)
    ]
    artifacts = {
        "objects": [
            {
                "objectUri": "demo-object://sha256/" + "d" * 64,
                "sha256": "d" * 64,
                "sizeBytes": 4,
                "mediaType": "audio/wav",
                "artifactOriginCommit": "0334abe",
            }
        ],
        "caseRecords": cases,
    }
    return handoff, report, artifacts


class LedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.db = Path(self.temporary.name) / "ledger.sqlite3"

    def test_duplicate_import_reuses_without_new_jobs(self) -> None:
        ledger = CloudJobLedger(self.db)
        handoff, report, artifacts = fixture_contract()
        first = import_records(ledger, handoff, report, artifacts)
        second = import_records(ledger, handoff, report, artifacts)
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertEqual(1, ledger.counts()["jobs"])
        self.assertEqual(12, len([r for r in ledger.rows("releases") if r["case_id"]]))
        ledger.close()
        reopened = CloudJobLedger(self.db)
        self.assertEqual(1, reopened.counts()["jobs"])
        reopened.close()

    def test_changed_contract_for_same_java_job_is_rejected(self) -> None:
        ledger = CloudJobLedger(self.db)
        handoff, report, artifacts = fixture_contract()
        import_records(ledger, handoff, report, artifacts)
        changed = copy.deepcopy(handoff)
        changed["jobs"][0]["requestFingerprint"] = "e" * 64
        with self.assertRaises(ContractConflict):
            import_records(ledger, changed, report, artifacts)
        ledger.close()

    def test_expired_lease_increments_fence_and_rejects_old_writer(self) -> None:
        ledger = CloudJobLedger(self.db)
        token_a = ledger.acquire_lease("job:1", "worker-A", 1, now=10)
        with self.assertRaises(LeaseConflict):
            ledger.acquire_lease("job:1", "worker-B", 1, now=10.5)
        token_b = ledger.acquire_lease("job:1", "worker-B", 2, now=12)
        self.assertEqual(token_a + 1, token_b)
        with self.assertRaises(StaleFence):
            ledger.finalize("job:1", "worker-A", token_a, "release:1", "java-1", now=12)
        ledger.close()


class ClaimBoundaryTest(unittest.TestCase):
    def test_fixture_has_no_final_selection(self) -> None:
        _, report, artifacts = fixture_contract()
        self.assertEqual(0, report["finalSelectedCount"])
        self.assertEqual(
            0,
            sum(record["publishDecision"] == "FINAL_SELECTED" for record in artifacts["caseRecords"]),
        )


if __name__ == "__main__":
    unittest.main()
