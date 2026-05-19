import http from "k6/http";
import { check } from "k6";

export const options = {
  vus: 1,
  iterations: 3,
  thresholds: {
    checks: ["rate==1.0"],
    http_req_failed: ["rate==0"],
    http_req_duration: ["p(95)<750"],
  },
};

const BASE_URL = __ENV.BASE_URL || __ENV.API_BASE_URL || "http://host.docker.internal:8080";
const USER = __ENV.BASIC_AUTH_USER || __ENV.K6_USER || "contract-user";
const PASS = __ENV.BASIC_AUTH_PASSWORD || __ENV.K6_PASSWORD || "contract-pass";
const EXPECTED_CODE = "MEDIA_TASK_INVALID_REQUEST";

http.setResponseCallback(http.expectedStatuses(400));

function authHeaders() {
  const token = `${USER}:${PASS}`;
  return {
    Authorization: `Basic ${encoding.b64encode(token)}`,
    Accept: "application/problem+json, application/json",
  };
}

const encoding = {
  b64encode(input) {
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let str = String(input);
    let output = "";

    for (let block = 0, charCode, i = 0, map = chars;
         str.charAt(i | 0) || (map = "=", i % 1);
         output += map.charAt(63 & block >> 8 - i % 1 * 8)) {
      charCode = str.charCodeAt(i += 3 / 4);
      if (charCode > 0xff) {
        throw new Error("b64encode only supports Latin1 input");
      }
      block = block << 8 | charCode;
    }

    return output;
  },
};

const cases = [
  {
    name: "size_zero",
    path: "/api/media-tasks?size=0",
    expectedDetail: "size must be between 1 and 100",
  },
  {
    name: "size_too_large",
    path: "/api/media-tasks?size=101",
    expectedDetail: "size must be between 1 and 100",
  },
  {
    name: "bad_sort",
    path: "/api/media-tasks?sort=bad_sort",
    expectedDetail: "unsupported sort: bad_sort",
  },
];

export default function () {
  const c = cases[__ITER % cases.length];
  const res = http.get(`${BASE_URL}${c.path}`, { headers: authHeaders() });

  let body = {};
  try {
    body = res.json();
  } catch (e) {
    body = {};
  }

  check(res, {
    [`${c.name}: status is 400`]: (r) => r.status === 400,
    [`${c.name}: problem code is ${EXPECTED_CODE}`]: () => body.code === EXPECTED_CODE,
    [`${c.name}: detail matches`]: () => body.detail === c.expectedDetail,
  });
}

export function handleSummary(data) {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const out = {};
  out[`loadtest/reports/week11_k6_query_boundary_${stamp}.json`] = JSON.stringify(data, null, 2);
  out.stdout = JSON.stringify({
    schema_version: "week11_k6_query_boundary_v1",
    base_url: BASE_URL,
    expected_code: EXPECTED_CODE,
    checks_rate: data.metrics.checks && data.metrics.checks.values ? data.metrics.checks.values.rate : null,
    http_req_failed_rate: data.metrics.http_req_failed && data.metrics.http_req_failed.values ? data.metrics.http_req_failed.values.rate : null,
    http_req_duration_p95_ms: data.metrics.http_req_duration && data.metrics.http_req_duration.values ? data.metrics.http_req_duration.values["p(95)"] : null,
  }, null, 2) + "\n";
  return out;
}
