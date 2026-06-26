import { check } from 'k6';
import { Rate, Counter } from 'k6/metrics';

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    week17_consumer_smoke_pass_rate: ['rate==1'],
    week17_dashboard_ready_rate: ['rate==1'],
    week17_k6_threshold_ready_rate: ['rate==1'],
    week17_slo_boundary_ready_rate: ['rate==1'],
    week17_official_promtool_required_rate: ['rate==1'],
    week17_consumer_errors_total: ['count==0'],
  },
};

const report = JSON.parse(open('loadtest/reports/week17_observability_evidence_index_consumer_smoke.json'));

const consumerSmokePassRate = new Rate('week17_consumer_smoke_pass_rate');
const dashboardReadyRate = new Rate('week17_dashboard_ready_rate');
const k6ThresholdReadyRate = new Rate('week17_k6_threshold_ready_rate');
const sloBoundaryReadyRate = new Rate('week17_slo_boundary_ready_rate');
const officialPromtoolRequiredRate = new Rate('week17_official_promtool_required_rate');
const consumerErrorsTotal = new Counter('week17_consumer_errors_total');

function isEmptyArray(value) {
  return Array.isArray(value) && value.length === 0;
}

function bool(value) {
  return value === true;
}

export default function () {
  const consumerPass =
    report.decision === 'PASS_WEEK17_OBSERVABILITY_EVIDENCE_INDEX_CONSUMER_SMOKE' &&
    bool(report.readyForNextWeek17DashboardAggregation) &&
    bool(report.readyForNextWeek17K6ThresholdSmoke) &&
    bool(report.readyForNextWeek17SloBoundaryExplanation) &&
    bool(report.officialPromtoolStillRequired) &&
    isEmptyArray(report.errors) &&
    report.sourceDecisionCount >= 4 &&
    report.blockedClaimsCount === 8;

  const dashboardReady = bool(report.readyForNextWeek17DashboardAggregation);
  const k6ThresholdReady = bool(report.readyForNextWeek17K6ThresholdSmoke);
  const sloBoundaryReady = bool(report.readyForNextWeek17SloBoundaryExplanation);
  const officialPromtoolStillRequired = bool(report.officialPromtoolStillRequired);
  const errorCount = Array.isArray(report.errors) ? report.errors.length : 1;

  consumerSmokePassRate.add(consumerPass);
  dashboardReadyRate.add(dashboardReady);
  k6ThresholdReadyRate.add(k6ThresholdReady);
  sloBoundaryReadyRate.add(sloBoundaryReady);
  officialPromtoolRequiredRate.add(officialPromtoolStillRequired);
  consumerErrorsTotal.add(errorCount);

  check(report, {
    'consumer smoke decision is PASS': () => report.decision === 'PASS_WEEK17_OBSERVABILITY_EVIDENCE_INDEX_CONSUMER_SMOKE',
    'dashboard aggregation input is ready': () => dashboardReady,
    'k6 threshold smoke input is ready': () => k6ThresholdReady,
    'SLO boundary explanation input is ready': () => sloBoundaryReady,
    'official promtool is still required': () => officialPromtoolStillRequired,
    'consumer errors are empty': () => errorCount === 0,
    'source decisions are sufficient': () => report.sourceDecisionCount >= 4,
    'blocked claims are preserved': () => report.blockedClaimsCount === 8,
  });
}

export function handleSummary(data) {
  const thresholdEntries = Object.entries(data.metrics)
    .filter(([, metric]) => metric.thresholds)
    .map(([name, metric]) => [name, metric.thresholds]);

  const thresholdSummary = Object.fromEntries(thresholdEntries);

  const failedThresholds = [];
  for (const [metricName, thresholds] of thresholdEntries) {
    for (const [expr, result] of Object.entries(thresholds)) {
      if (result.ok !== true) {
        failedThresholds.push(`${metricName}:${expr}`);
      }
    }
  }

  const output = {
    schemaVersion: 'week17.observability_evidence_index.k6_threshold_smoke.v1',
    decision:
      failedThresholds.length === 0
        ? 'PASS_WEEK17_OBSERVABILITY_EVIDENCE_INDEX_K6_THRESHOLD_SMOKE'
        : 'BLOCK_WEEK17_OBSERVABILITY_EVIDENCE_INDEX_K6_THRESHOLD_SMOKE',
    inputReport: 'loadtest/reports/week17_observability_evidence_index_consumer_smoke.json',
    inputDecision: report.decision,
    readyForNextWeek17DashboardAggregation: report.readyForNextWeek17DashboardAggregation === true,
    readyForNextWeek17K6ThresholdSmoke: report.readyForNextWeek17K6ThresholdSmoke === true,
    readyForNextWeek17SloBoundaryExplanation: report.readyForNextWeek17SloBoundaryExplanation === true,
    officialPromtoolStillRequired: report.officialPromtoolStillRequired === true,
    sourceDecisionCount: report.sourceDecisionCount,
    blockedClaimsCount: report.blockedClaimsCount,
    failedThresholds,
    thresholds: thresholdSummary,
    blockedClaimsPreserved: report.blockedClaimsCount === 8,
    notes: [
      'This is an offline k6 threshold smoke over a persisted consumer-smoke artifact.',
      'This does not claim live HTTP load testing.',
      'This does not claim official promtool pass.',
      'This does not claim production SLO.',
    ],
  };

  return {
    'loadtest/reports/week17_observability_evidence_index_k6_threshold_smoke.json':
      JSON.stringify(output, null, 2) + '\n',
    stdout:
      `decision=${output.decision}\n` +
      `inputDecision=${output.inputDecision}\n` +
      `failedThresholds=${JSON.stringify(output.failedThresholds)}\n` +
      `officialPromtoolStillRequired=${output.officialPromtoolStillRequired}\n`,
  };
}