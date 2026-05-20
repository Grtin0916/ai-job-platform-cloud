import http from 'k6/http';
import { check } from 'k6';
import encoding from 'k6/encoding';

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    http_req_failed: ['rate==0'],
    http_req_duration: ['p(95)<200'],
    checks: ['rate==1'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://host.docker.internal:8080';
const USERNAME = __ENV.K6_USER || 'k6-user';
const PASSWORD = __ENV.K6_PASSWORD || 'k6-password';

const EXPECTED_TASK_ID = 'week11-k6-seed-created-001';
const EXPECTED_ARTIFACT_URI = 'mainbase://artifacts/manifests/week11_crossrepo_task_bridge.json';
const EXPECTED_EVAL_SUMMARY_URI = 'mainbase://artifacts/evals/week11_eval_quality_gate_v0.json';
const EXPECTED_QUALITY_GATE_STATUS = 'PASS';

function basicAuthHeaders() {
  const token = encoding.b64encode(`${USERNAME}:${PASSWORD}`);
  return {
    headers: {
      Authorization: `Basic ${token}`,
      Accept: 'application/json',
    },
  };
}

export default function () {
  const url = `${BASE_URL}/api/media-tasks?page=0&size=5&status=CREATED&sort=created_at_desc`;
  const res = http.get(url, basicAuthHeaders());

  let body = {};
  try {
    body = res.json();
  } catch (e) {
    body = {};
  }

  const content = Array.isArray(body.content) ? body.content : [];
  const target = content.find((item) => item && item.id === EXPECTED_TASK_ID) || {};

  check(res, {
    'status is 200': (r) => r.status === 200,
    'content is array': () => Array.isArray(content),
    'seed task is visible': () => content.some((item) => item && item.id === EXPECTED_TASK_ID),
    'artifactUri is bound to mainbase bridge': () => target.artifactUri === EXPECTED_ARTIFACT_URI,
    'evalSummaryUri is bound to quality gate': () => target.evalSummaryUri === EXPECTED_EVAL_SUMMARY_URI,
    'qualityGateStatus is PASS': () => target.qualityGateStatus === EXPECTED_QUALITY_GATE_STATUS,
  });
}