import http from "k6/http";
import { check } from "k6";
import { Rate } from "k6/metrics";

const boundaryPreserved = new Rate("ranker_boundary_preserved");

export const options = {
  vus: 1,
  iterations: 10,
  thresholds: {
    checks: ["rate>0.99"],
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<750"],
    ranker_boundary_preserved: ["rate>0.99"],
  },
};

export default function () {
  const base = __ENV.RANKER_API_BASE || "http://127.0.0.1:8080";
  const response = http.get(`${base}/api/ranker-results/fb_001_tuesday_repair`);
  const valid = check(response, {
    "status is 200": (r) => r.status === 200,
    "blocked recommendation is unavailable": (r) => r.json("recommendationStatus") === "UNAVAILABLE",
    "publish decision remains provisional": (r) => r.json("publishDecision") === "PROVISIONAL_SELECTED",
    "no final mutation": (r) => r.json("finalSelectedMutationCount") === 0,
  });
  boundaryPreserved.add(valid);
}
