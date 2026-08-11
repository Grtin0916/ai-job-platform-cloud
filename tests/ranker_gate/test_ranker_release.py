import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ranker_gate"))

from verify_ranker_release import verify


class BuiltReleaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.release = ROOT / "artifacts/demo/w21_ranker_release_20260731"
        cls.archive = ROOT / "artifacts/demo/w21_ranker_release_20260731.zip"

    def test_release_integrity(self):
        self.assertTrue(verify(self.release, self.archive)["verified"])

    def test_release_has_four_playable_provisional_examples(self):
        report = verify(self.release, self.archive)
        self.assertEqual(4, report["playableAudioCount"])
        self.assertEqual(0, report["unreadableAudioCount"])

    def test_release_is_hold_with_no_final_selection(self):
        manifest = json.loads((self.release / "manifest.json").read_text())
        self.assertEqual("HOLD_HUMAN_REVIEW", manifest["releaseDecision"])
        self.assertEqual(0, manifest["finalSelectedCount"])

    def test_audio_claim_boundary_denies_ranker_winner(self):
        boundary = json.loads((self.release / "claim-boundary.json").read_text())
        self.assertTrue(boundary["audioExamplesAreW20Provisional"])
        self.assertFalse(boundary["audioExamplesAreRankerRecommendations"])
        self.assertFalse(boundary["audioExamplesProveHumanPreference"])


if __name__ == "__main__":
    unittest.main()
