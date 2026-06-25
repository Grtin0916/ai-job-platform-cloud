#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ACTION_GATE = ROOT / "loadtest/reports/week17_layer_mix_v0_action_gate.json"
RULES_OUT = ROOT / "observability/prometheus/week17_layer_mix_v0_action_gate_alert_rules.yml"
TEST_OUT = ROOT / "observability/prometheus/week17_layer_mix_v0_action_gate_alert_rule_test.yml"
REPORT_OUT = ROOT / "loadtest/reports/week17_layer_mix_v0_action_gate_alert_rules_report.json"


def git_head(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"missing input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    d = load_json(ACTION_GATE)

    if d.get("decision") != "PASS_WEEK17_LAYER_MIX_V0_ACTION_GATE_WITH_NEGATIVE_CONTROLS":
        raise RuntimeError(f"unexpected action gate decision: {d.get('decision')}")
    if d.get("scenarioTotal") != 5:
        raise RuntimeError(f"unexpected scenarioTotal: {d.get('scenarioTotal')}")
    if d.get("passScenarioTotal") != 1:
        raise RuntimeError(f"unexpected passScenarioTotal: {d.get('passScenarioTotal')}")
    if d.get("blockScenarioTotal") != 4:
        raise RuntimeError(f"unexpected blockScenarioTotal: {d.get('blockScenarioTotal')}")
    if d.get("negativeControlsAllBlocked") is not True:
        raise RuntimeError("negative controls were not all blocked")

    cloud_head = git_head(ROOT)

    RULES_OUT.parent.mkdir(parents=True, exist_ok=True)
    TEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)

    rules = """groups:
- name: week17_layer_mix_v0_action_gate
  rules:
  - alert: Week17LayerMixV0ActionGateBlocked
    expr: week17_layer_mix_v0_action_gate_block{scenario_kind="negative_control"} == 1
    for: 0m
    labels:
      severity: warning
      stage: week17
      component: layer_mix_v0
    annotations:
      summary: "Week17 layer mix v0 action gate blocked a negative-control scenario"
      description: "The layer mix v0 action gate blocked scenario {{ $labels.scenario }} with action {{ $labels.action }}."

  - alert: Week17LayerMixV0ActionGateIssueDetected
    expr: week17_layer_mix_v0_action_gate_issue_total{scenario_kind="negative_control"} > 0
    for: 0m
    labels:
      severity: warning
      stage: week17
      component: layer_mix_v0
    annotations:
      summary: "Week17 layer mix v0 action gate detected issues"
      description: "The layer mix v0 action gate detected {{ $value }} issue(s) for scenario {{ $labels.scenario }}."

  - alert: Week17LayerMixV0ClipRisk
    expr: week17_layer_mix_v0_action_gate_clip_rate{scenario_kind="negative_control"} > 0
    for: 0m
    labels:
      severity: critical
      stage: week17
      component: layer_mix_v0
    annotations:
      summary: "Week17 layer mix v0 clip risk detected"
      description: "Clip rate is above zero for scenario {{ $labels.scenario }}."

  - alert: Week17LayerMixV0HealthyCaseUnexpectedlyBlocked
    expr: week17_layer_mix_v0_action_gate_block{scenario="real_current_healthy_preview",scenario_kind="real_current"} == 1
    for: 0m
    labels:
      severity: critical
      stage: week17
      component: layer_mix_v0
    annotations:
      summary: "Week17 layer mix v0 healthy preview was unexpectedly blocked"
      description: "The real current healthy preview should remain allowed as placeholder-control preview only."
"""

    test = """rule_files:
  - week17_layer_mix_v0_action_gate_alert_rules.yml

evaluation_interval: 1m

tests:
- interval: 1m
  input_series:
  - series: 'week17_layer_mix_v0_action_gate_block{scenario="real_current_healthy_preview",scenario_kind="real_current",action="ALLOW_PLACEHOLDER_CONTROL_PLATFORM_PREVIEW_ONLY",decision="PASS_WEEK17_LAYER_MIX_V0_ACTION_GATE",source_java_head="d6928dc",source_mainbase_head="d9a6df0"}'
    values: '0'
  - series: 'week17_layer_mix_v0_action_gate_issue_total{scenario="real_current_healthy_preview",scenario_kind="real_current",action="ALLOW_PLACEHOLDER_CONTROL_PLATFORM_PREVIEW_ONLY",decision="PASS_WEEK17_LAYER_MIX_V0_ACTION_GATE",source_java_head="d6928dc",source_mainbase_head="d9a6df0"}'
    values: '0'
  - series: 'week17_layer_mix_v0_action_gate_clip_rate{scenario="real_current_healthy_preview",scenario_kind="real_current",action="ALLOW_PLACEHOLDER_CONTROL_PLATFORM_PREVIEW_ONLY",decision="PASS_WEEK17_LAYER_MIX_V0_ACTION_GATE",source_java_head="d6928dc",source_mainbase_head="d9a6df0"}'
    values: '0'

  - series: 'week17_layer_mix_v0_action_gate_block{scenario="synthetic_high_clip_rate",scenario_kind="negative_control",action="BLOCK_AUDIO_CLIPPING_RISK",decision="BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE",source_java_head="d6928dc",source_mainbase_head="d9a6df0"}'
    values: '1'
  - series: 'week17_layer_mix_v0_action_gate_issue_total{scenario="synthetic_high_clip_rate",scenario_kind="negative_control",action="BLOCK_AUDIO_CLIPPING_RISK",decision="BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE",source_java_head="d6928dc",source_mainbase_head="d9a6df0"}'
    values: '1'
  - series: 'week17_layer_mix_v0_action_gate_clip_rate{scenario="synthetic_high_clip_rate",scenario_kind="negative_control",action="BLOCK_AUDIO_CLIPPING_RISK",decision="BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE",source_java_head="d6928dc",source_mainbase_head="d9a6df0"}'
    values: '0.025'

  - series: 'week17_layer_mix_v0_action_gate_block{scenario="synthetic_missing_track",scenario_kind="negative_control",action="BLOCK_INCOMPLETE_LAYER_INPUT",decision="BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE",source_java_head="d6928dc",source_mainbase_head="d9a6df0"}'
    values: '1'
  - series: 'week17_layer_mix_v0_action_gate_issue_total{scenario="synthetic_missing_track",scenario_kind="negative_control",action="BLOCK_INCOMPLETE_LAYER_INPUT",decision="BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE",source_java_head="d6928dc",source_mainbase_head="d9a6df0"}'
    values: '1'
  - series: 'week17_layer_mix_v0_action_gate_clip_rate{scenario="synthetic_missing_track",scenario_kind="negative_control",action="BLOCK_INCOMPLETE_LAYER_INPUT",decision="BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE",source_java_head="d6928dc",source_mainbase_head="d9a6df0"}'
    values: '0'

  - series: 'week17_layer_mix_v0_action_gate_block{scenario="synthetic_low_rms_silentish",scenario_kind="negative_control",action="BLOCK_INVALID_AUDIO_ENERGY",decision="BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE",source_java_head="d6928dc",source_mainbase_head="d9a6df0"}'
    values: '1'
  - series: 'week17_layer_mix_v0_action_gate_issue_total{scenario="synthetic_low_rms_silentish",scenario_kind="negative_control",action="BLOCK_INVALID_AUDIO_ENERGY",decision="BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE",source_java_head="d6928dc",source_mainbase_head="d9a6df0"}'
    values: '1'
  - series: 'week17_layer_mix_v0_action_gate_clip_rate{scenario="synthetic_low_rms_silentish",scenario_kind="negative_control",action="BLOCK_INVALID_AUDIO_ENERGY",decision="BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE",source_java_head="d6928dc",source_mainbase_head="d9a6df0"}'
    values: '0'

  - series: 'week17_layer_mix_v0_action_gate_block{scenario="synthetic_final_mix_overclaim",scenario_kind="negative_control",action="BLOCK_OVERCLAIMED_CAPABILITY",decision="BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE",source_java_head="d6928dc",source_mainbase_head="d9a6df0"}'
    values: '1'
  - series: 'week17_layer_mix_v0_action_gate_issue_total{scenario="synthetic_final_mix_overclaim",scenario_kind="negative_control",action="BLOCK_OVERCLAIMED_CAPABILITY",decision="BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE",source_java_head="d6928dc",source_mainbase_head="d9a6df0"}'
    values: '1'
  - series: 'week17_layer_mix_v0_action_gate_clip_rate{scenario="synthetic_final_mix_overclaim",scenario_kind="negative_control",action="BLOCK_OVERCLAIMED_CAPABILITY",decision="BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE",source_java_head="d6928dc",source_mainbase_head="d9a6df0"}'
    values: '0'

  alert_rule_test:
  - eval_time: 0m
    alertname: Week17LayerMixV0ActionGateBlocked
    exp_alerts:
    - exp_labels:
        severity: warning
        stage: week17
        component: layer_mix_v0
        scenario: synthetic_high_clip_rate
        scenario_kind: negative_control
        action: BLOCK_AUDIO_CLIPPING_RISK
        decision: BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE
        source_java_head: d6928dc
        source_mainbase_head: d9a6df0
      exp_annotations:
        summary: "Week17 layer mix v0 action gate blocked a negative-control scenario"
        description: "The layer mix v0 action gate blocked scenario synthetic_high_clip_rate with action BLOCK_AUDIO_CLIPPING_RISK."
    - exp_labels:
        severity: warning
        stage: week17
        component: layer_mix_v0
        scenario: synthetic_missing_track
        scenario_kind: negative_control
        action: BLOCK_INCOMPLETE_LAYER_INPUT
        decision: BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE
        source_java_head: d6928dc
        source_mainbase_head: d9a6df0
      exp_annotations:
        summary: "Week17 layer mix v0 action gate blocked a negative-control scenario"
        description: "The layer mix v0 action gate blocked scenario synthetic_missing_track with action BLOCK_INCOMPLETE_LAYER_INPUT."
    - exp_labels:
        severity: warning
        stage: week17
        component: layer_mix_v0
        scenario: synthetic_low_rms_silentish
        scenario_kind: negative_control
        action: BLOCK_INVALID_AUDIO_ENERGY
        decision: BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE
        source_java_head: d6928dc
        source_mainbase_head: d9a6df0
      exp_annotations:
        summary: "Week17 layer mix v0 action gate blocked a negative-control scenario"
        description: "The layer mix v0 action gate blocked scenario synthetic_low_rms_silentish with action BLOCK_INVALID_AUDIO_ENERGY."
    - exp_labels:
        severity: warning
        stage: week17
        component: layer_mix_v0
        scenario: synthetic_final_mix_overclaim
        scenario_kind: negative_control
        action: BLOCK_OVERCLAIMED_CAPABILITY
        decision: BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE
        source_java_head: d6928dc
        source_mainbase_head: d9a6df0
      exp_annotations:
        summary: "Week17 layer mix v0 action gate blocked a negative-control scenario"
        description: "The layer mix v0 action gate blocked scenario synthetic_final_mix_overclaim with action BLOCK_OVERCLAIMED_CAPABILITY."

  - eval_time: 0m
    alertname: Week17LayerMixV0ClipRisk
    exp_alerts:
    - exp_labels:
        severity: critical
        stage: week17
        component: layer_mix_v0
        scenario: synthetic_high_clip_rate
        scenario_kind: negative_control
        action: BLOCK_AUDIO_CLIPPING_RISK
        decision: BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE
        source_java_head: d6928dc
        source_mainbase_head: d9a6df0
      exp_annotations:
        summary: "Week17 layer mix v0 clip risk detected"
        description: "Clip rate is above zero for scenario synthetic_high_clip_rate."

  - eval_time: 0m
    alertname: Week17LayerMixV0HealthyCaseUnexpectedlyBlocked
    exp_alerts: []
"""

    RULES_OUT.write_text(rules, encoding="utf-8")
    TEST_OUT.write_text(test, encoding="utf-8")

    report = {
        "schemaVersion": "week17.layer_mix_v0.action_gate_alert_rules_report.v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "decision": "READY_TO_RUN_PROMTOOL_ALERT_RULE_TEST",
        "cloudHeadBeforeCommit": cloud_head,
        "sourceActionGate": str(ACTION_GATE.relative_to(ROOT)),
        "rulesFile": str(RULES_OUT.relative_to(ROOT)),
        "testFile": str(TEST_OUT.relative_to(ROOT)),
        "expectedNegativeControlAlerts": 4,
        "expectedClipRiskAlerts": 1,
        "expectedHealthyUnexpectedlyBlockedAlerts": 0,
        "livePrometheusScrapeClaimed": False,
        "alertmanagerRoutingClaimed": False,
        "productionPagingClaimed": False,
    }
    REPORT_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "decision": report["decision"],
        "rulesFile": report["rulesFile"],
        "testFile": report["testFile"],
        "reportFile": str(REPORT_OUT.relative_to(ROOT)),
        "expectedNegativeControlAlerts": report["expectedNegativeControlAlerts"],
        "expectedClipRiskAlerts": report["expectedClipRiskAlerts"],
    }, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())