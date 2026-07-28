import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const terminalSuccess = new Rate("demo_job_terminal_success");
const claimBoundaryPreserved = new Rate("demo_job_claim_boundary_preserved");
const baseUrl = __ENV.BASE_URL || "http://host.docker.internal:8080";

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    checks: ["rate>0.99"],
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000"],
    demo_job_terminal_success: ["rate>0.99"],
    demo_job_claim_boundary_preserved: ["rate>0.99"],
  },
};

function createJob(key, body) {
  return http.post(`${baseUrl}/api/demo-jobs`, JSON.stringify(body), {
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": key,
    },
  });
}

function awaitTerminal(jobId) {
  for (let i = 0; i < 100; i += 1) {
    const response = http.get(`${baseUrl}/api/demo-jobs/${jobId}`);
    if (response.status !== 200) {
      return response;
    }
    const status = response.json("executionStatus");
    if (["SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED", "BLOCKED"].includes(status)) {
      return response;
    }
    sleep(0.1);
  }
  return null;
}

export default function () {
  const key = `w20-k6-replay-${__VU}-${__ITER}`;
  const replayBody = {
    caseId: "fb_001_tuesday_repair",
    mode: "REPLAY",
    timeoutSeconds: 120,
    resume: true,
  };
  const created = createJob(key, replayBody);
  check(created, { "replay accepted": (r) => r.status === 202 });
  const jobId = created.json("jobId");
  const terminal = jobId ? awaitTerminal(jobId) : null;
  const succeeded = terminal !== null && terminal.json("executionStatus") === "SUCCEEDED";
  terminalSuccess.add(succeeded);

  const result = succeeded ? http.get(`${baseUrl}/api/demo-jobs/${jobId}/result`) : null;
  const boundary =
    result !== null &&
    result.status === 200 &&
    result.json("publishDecision") === "PROVISIONAL_SELECTED" &&
    result.json("finalSelected") === false &&
    result.json("proxyEvidenceOnly") === true;
  claimBoundaryPreserved.add(boundary);
  check(result || { status: 0 }, { "result keeps provisional boundary": () => boundary });

  const repeated = createJob(key, replayBody);
  check(repeated, {
    "same idempotency key reuses job": (r) => r.status === 202 && r.json("jobId") === jobId,
  });
  const conflictBody = Object.assign({}, replayBody, { timeoutSeconds: 121 });
  check(createJob(key, conflictBody), { "changed request conflicts": (r) => r.status === 409 });

  const mixed = createJob(`w20-k6-mixed-${__VU}-${__ITER}`, {
    caseId: "fb_001_tuesday_repair",
    mode: "MIXED",
    timeoutSeconds: 120,
    resume: true,
  });
  check(mixed, {
    "mixed capability is blocked": (r) =>
      r.status === 200 && r.json("executionStatus") === "BLOCKED" && r.json("attempts").length === 0,
  });

  const rejected = createJob(`w20-k6-rejected-${__VU}-${__ITER}`, {
    caseId: "fb_004_transplant_v1",
    mode: "REPLAY",
    timeoutSeconds: 120,
    resume: true,
  });
  check(rejected, {
    "rejected case does not start runner": (r) =>
      r.status === 200 &&
      r.json("executionStatus") === "BLOCKED" &&
      r.json("publishDecision") === "REPAIR_REJECTED" &&
      r.json("attempts").length === 0,
  });
}
