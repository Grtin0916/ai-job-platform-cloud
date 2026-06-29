#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENDPOINTS = {
    "model_race_seed": "/api/week17/model-race-seed",
    "repair_seed": "/api/week17/repair-seed",
    "summary": "/api/week17/model-race-seed/summary",
}


def fetch_json(url: str, timeout_s: float = 5.0) -> tuple[bool, int, dict[str, Any] | None, str, float]:
    started = time.time()
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8")
            elapsed_ms = (time.time() - started) * 1000.0
            return True, resp.status, json.loads(body), "", elapsed_ms
    except urllib.error.HTTPError as e:
        elapsed_ms = (time.time() - started) * 1000.0
        return False, int(e.code), None, str(e), elapsed_ms
    except Exception as e:
        elapsed_ms = (time.time() - started) * 1000.0
        return False, 0, None, str(e), elapsed_ms


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:18080")
    ap.add_argument("--out-root", default="artifacts/demo/week17_java_live_consumer_smoke")
    args = ap.parse_args()

    out_root = Path(args.out_root)
    rows = {}

    for name, path in ENDPOINTS.items():
        ok, status, payload, error, elapsed_ms = fetch_json(args.base_url.rstrip("/") + path)
        rows[name] = {
            "endpoint": path,
            "ok": ok,
            "status": status,
            "elapsed_ms": round(elapsed_ms, 2),
            "error": error,
            "payload": payload,
        }

    model = rows["model_race_seed"]["payload"] or {}
    repair = rows["repair_seed"]["payload"] or {}
    summary_payload = rows["summary"]["payload"] or {}

    checks = {
        "all_http_2xx": all(r["ok"] and 200 <= int(r["status"]) < 300 for r in rows.values()),
        "model_schema_ok": model.get("schema_version") == "model_race_seed.v0.1",
        "repair_schema_ok": repair.get("schema_version") == "repair_seed.v0.1",
        "summary_source_ok": summary_payload.get("source") == "mainbase",
        "model_result_count_ok": len(model.get("results", [])) == 6,
        "repair_result_count_ok": len(repair.get("results", [])) == 1,
        "repair_closed_ok": summary_payload.get("repair_closed") is True,
    }

    decision = "PASS_JAVA_LIVE_CONSUMER_SMOKE" if all(checks.values()) else "FAIL_JAVA_LIVE_CONSUMER_SMOKE"

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "base_url": args.base_url,
        "checks": checks,
        "observed": {
            "model_race_decision": model.get("decision"),
            "repair_decision": repair.get("decision"),
            "model_result_count": len(model.get("results", [])),
            "repair_result_count": len(repair.get("results", [])),
            "repair_closed": summary_payload.get("repair_closed"),
            "max_elapsed_ms": max((r["elapsed_ms"] for r in rows.values()), default=0.0),
        },
        "runtime_boundary": {
            "k6_used": False,
            "claim": "direct urllib HTTP smoke only; no k6 threshold or production SLO claimed",
        },
        "responses": rows,
    }

    write_json(out_root / "week17_java_live_consumer_smoke.json", report)
    write_json(Path("loadtest/reports/week17_java_live_consumer_smoke.json"), report)

    metrics = [
        f'week17_java_live_consumer_pass {1 if decision.startswith("PASS") else 0}',
        f'week17_java_live_model_result_count {len(model.get("results", []))}',
        f'week17_java_live_repair_result_count {len(repair.get("results", []))}',
        f'week17_java_live_repair_closed {1 if summary_payload.get("repair_closed") is True else 0}',
        f'week17_java_live_max_elapsed_ms {report["observed"]["max_elapsed_ms"]}',
    ]
    Path("loadtest/reports/week17_java_live_consumer_smoke_metrics.prom").write_text(
        "\n".join(metrics) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({k: report[k] for k in ["decision", "base_url", "checks", "observed", "runtime_boundary"]}, ensure_ascii=False, indent=2))
    return 0 if decision.startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())