import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ranker_gate"))

from build_ranker_observability import build
from inject_ranker_gate_failures import run
from test_ranker_contract import snapshot
from validate_metric_cardinality import validate


class MissingnessMetricTest(unittest.TestCase):
    def setUp(self):
        self.metrics, self.report = build(snapshot())

    def test_availability_is_zero_without_quality_sample(self):
        self.assertIn('ranker_metric_available{metric="oof_accuracy"} 0', self.metrics)
        self.assertNotIn("ranker_oof_accuracy ", self.metrics)
        self.assertNotIn("ranker_brier_score ", self.metrics)

    def test_hold_is_not_an_alert(self):
        self.assertEqual(0, self.report["normalHoldAlertCount"])
        self.assertEqual("HOLD_HUMAN_REVIEW", self.report["releaseDecision"])

    def test_metric_labels_are_low_cardinality(self):
        report = validate(self.metrics)
        self.assertTrue(report["valid"])
        self.assertEqual(0, report["forbiddenLabelCount"])

    def test_metric_type_declarations_are_unique(self):
        declarations = [line for line in self.metrics.splitlines() if line.startswith("# TYPE ")]
        names = [line.split()[2] for line in declarations]
        self.assertEqual(len(names), len(set(names)))

    def test_four_faults_are_detected(self):
        report = run(snapshot())
        self.assertEqual(4, report["faultInjectionCount"])
        self.assertEqual(4, report["faultDetectionCount"])
        self.assertEqual(0, report["falsePromotionCount"])

    def test_dashboard_has_twelve_panels_and_stable_uid(self):
        dashboard = json.loads((ROOT / "observability/grafana/dashboards/w21-ranker-observatory.json").read_text())
        self.assertEqual("w21-ranker-observatory", dashboard["uid"])
        self.assertEqual(12, len(dashboard["panels"]))

    def test_rules_define_exact_seven_alerts(self):
        text = (ROOT / "observability/prometheus/w21_ranker_rules.yml").read_text()
        self.assertEqual(7, text.count("- alert:"))
        self.assertNotIn("NoRankerModel", text)
        self.assertNotIn("HumanReviewPending", text)


if __name__ == "__main__":
    unittest.main()
