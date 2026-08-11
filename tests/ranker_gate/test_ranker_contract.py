import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ranker_gate"))

from ranker_contract import validate_snapshot
from ranker_gate_state import GATE_ORDER, evaluate, injected


def snapshot() -> dict:
    return {
        "ranker": {
            "promotionStatus": "DATA_BLOCKED", "modelPresent": False,
            "oofAvailable": False, "recommendationCount": 0,
            "reviewRows": 48, "reviewSubmittedCount": 0,
            "humanReviewCompleted": False, "finalSelectedMutationCount": 0,
        },
        "registry": {"versionCount": 1},
        "artifactIntegrity": {
            "ready": True, "crossRepositoryDigestMatch": True,
        },
        "claimBoundary": {"productionWorkflowVerified": False},
    }


class ContractInvariantTest(unittest.TestCase):
    def test_valid_blocked_snapshot(self):
        validate_snapshot(snapshot())

    def test_blocked_model_is_rejected(self):
        value = snapshot(); value["ranker"]["modelPresent"] = True
        with self.assertRaisesRegex(ValueError, "learned outputs"):
            validate_snapshot(value)

    def test_blocked_oof_is_rejected(self):
        value = snapshot(); value["ranker"]["oofAvailable"] = True
        with self.assertRaisesRegex(ValueError, "learned outputs"):
            validate_snapshot(value)

    def test_blocked_recommendation_is_rejected(self):
        value = snapshot(); value["ranker"]["recommendationCount"] = 1
        with self.assertRaisesRegex(ValueError, "learned outputs"):
            validate_snapshot(value)

    def test_final_mutation_is_rejected(self):
        value = snapshot(); value["ranker"]["finalSelectedMutationCount"] = 1
        with self.assertRaisesRegex(ValueError, "final selection"):
            validate_snapshot(value)

    def test_integrity_failure_is_rejected(self):
        value = snapshot(); value["artifactIntegrity"]["ready"] = False
        with self.assertRaisesRegex(ValueError, "checksum"):
            validate_snapshot(value)


class MonotonicGateTest(unittest.TestCase):
    def test_baseline_holds_for_human_review(self):
        result = evaluate(snapshot())
        self.assertEqual("HOLD_HUMAN_REVIEW", result["overallDecision"])
        self.assertEqual(0, result["falsePromotionCount"])

    def test_gate_has_exact_ten_axes(self):
        self.assertEqual(10, len(GATE_ORDER))
        self.assertEqual(set(GATE_ORDER), set(evaluate(snapshot())["gates"]))

    def test_upstream_missing_axes_are_false(self):
        gates = evaluate(snapshot())["gates"]
        self.assertFalse(gates["preferenceDataReady"])
        self.assertFalse(gates["modelAvailable"])
        self.assertFalse(gates["finalSelectionReady"])

    def test_blocked_recommendation_detected(self):
        value = injected(snapshot(), "blocked_contains_recommendations")
        self.assertEqual("BLOCK_CONTRACT_DRIFT", evaluate(value)["overallDecision"])

    def test_blocked_model_detected(self):
        value = injected(snapshot(), "blocked_contains_model")
        self.assertEqual("BLOCK_INVALID_PROMOTION", evaluate(value)["overallDecision"])

    def test_final_without_review_detected(self):
        value = injected(snapshot(), "final_without_human_review")
        self.assertEqual("BLOCK_HUMAN_GATE_VIOLATION", evaluate(value)["overallDecision"])

    def test_digest_mismatch_detected(self):
        value = injected(snapshot(), "bundle_digest_mismatch")
        self.assertEqual("BLOCK_ARTIFACT_INTEGRITY", evaluate(value)["overallDecision"])

    def test_unknown_fault_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown scenario"):
            injected(snapshot(), "unknown")


if __name__ == "__main__":
    unittest.main()
