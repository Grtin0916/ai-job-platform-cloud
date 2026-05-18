import http from 'k6/http';

const HAS_BASIC_AUTH = Boolean(__ENV.BASIC_USER && __ENV.BASIC_PASS);

http.setResponseCallback(
  HAS_BASIC_AUTH
    ? http.expectedStatuses({ min: 200, max: 399 })
    : http.expectedStatuses({ min: 200, max: 399 }, 401, 403)
);
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8080';
const BASIC_USER = __ENV.BASIC_USER || '';
const BASIC_PASS = __ENV.BASIC_PASS || '';
const SEEDED_TASK_ID = __ENV.SEEDED_TASK_ID || 'week11-k6-seed-created-001';

export const options = {
  vus: Number(__ENV.VUS || 2),
  duration: __ENV.DURATION || '30s',
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<750'],
    checks: ['rate>0.95'],
  },
};

function authParams() {
  if (BASIC_USER && BASIC_PASS) {
    return {
      auth: 'basic',
      headers: {
        Authorization: `Basic ${encoding.b64encode(`${BASIC_USER}:${BASIC_PASS}`)}`,
      },
    };
  }
  return {};
}

// k6 does not expose btoa in all runtimes; use a small local encoder.
const encoding = {
  chars: 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/',
  b64encode(input) {
    const bytes = Array.from(input).map((c) => c.charCodeAt(0));
    let out = '';
    for (let i = 0; i < bytes.length; i += 3) {
      const b0 = bytes[i];
      const b1 = bytes[i + 1] ?? 0;
      const b2 = bytes[i + 2] ?? 0;
      const triplet = (b0 << 16) | (b1 << 8) | b2;
      out += this.chars[(triplet >> 18) & 63];
      out += this.chars[(triplet >> 12) & 63];
      out += i + 1 < bytes.length ? this.chars[(triplet >> 6) & 63] : '=';
      out += i + 2 < bytes.length ? this.chars[triplet & 63] : '=';
    }
    return out;
  },
};

export default function () {
  const health = http.get(`${BASE_URL}/actuator/health`);

  check(health, {
    'health status is 200': (r) => r.status === 200,
    'health has body': (r) => r.body && r.body.length > 0,
  });

  const queryUrl = `${BASE_URL}/api/media-tasks?page=0&size=5&status=CREATED&sort=created_at_desc`;
  const query = http.get(queryUrl, authParams());

  check(query, {
    'query status matches auth mode': (r) => {
      if (HAS_BASIC_AUTH) return r.status === 200;
      return [200, 401, 403].includes(r.status);
    },
    'query does not return 5xx': (r) => r.status < 500,
    'query json shape when 200': (r) => {
      if (r.status !== 200) return true;
      try {
        const body = r.json();
        return Array.isArray(body.content)
          && typeof body.page === 'number'
          && typeof body.size === 'number'
          && typeof body.totalElements === 'number'
          && body.status === 'CREATED'
          && body.sort === 'created_at_desc';
      } catch (_) {
        return false;
      }
    },
    'query returns seeded task when authenticated': (r) => {
      if (!HAS_BASIC_AUTH) return true;
      if (r.status !== 200) return false;
      try {
        const body = r.json();
        return Array.isArray(body.content)
          && body.content.some((item) => item.id === SEEDED_TASK_ID && item.status === 'CREATED');
      } catch (_) {
        return false;
      }
    },
  });

  sleep(1);
}
