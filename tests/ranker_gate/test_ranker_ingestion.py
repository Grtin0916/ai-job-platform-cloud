import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT.parent
sys.path.insert(0, str(ROOT / "scripts/ranker_gate"))

from ranker_contract import build_snapshot


class RealCrossRepositoryIngestionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value = build_snapshot(
            WORKSPACE / "audio_engineering_repo_skeleton_v1",
            WORKSPACE / "media-task-platform-java",
            ROOT,
            Path("reports/ranker_delivery_20260730.json"),
            Path("artifacts/manifests/w21_ranker_version_report.json"),
            Path("artifacts/runtime/rankers/ranker-events.jsonl"),
        )

    def test_real_digest_matches(self):
        self.assertTrue(self.value["artifactIntegrity"]["crossRepositoryDigestMatch"])

    def test_real_checksums_are_complete(self):
        integrity = self.value["artifactIntegrity"]
        self.assertEqual(4, integrity["checksumCount"])
        self.assertEqual(4, integrity["checksumVerifiedCount"])

    def test_real_status_is_blocked_without_outputs(self):
        ranker = self.value["ranker"]
        self.assertEqual("DATA_BLOCKED", ranker["promotionStatus"])
        self.assertFalse(ranker["modelPresent"])
        self.assertFalse(ranker["oofAvailable"])
        self.assertEqual(0, ranker["recommendationCount"])

    def test_real_review_and_final_state_remain_empty(self):
        ranker = self.value["ranker"]
        self.assertEqual(48, ranker["reviewRows"])
        self.assertEqual(0, ranker["reviewSubmittedCount"])
        self.assertEqual(0, ranker["finalSelectedMutationCount"])

    def test_registry_has_registered_and_reused_events(self):
        self.assertEqual("REGISTERED_AND_REUSED", self.value["registry"]["registryImportResult"])
        self.assertEqual(0, self.value["registry"]["versionConflictCount"])


if __name__ == "__main__":
    unittest.main()
