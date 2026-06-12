#!/usr/bin/env python3
"""
Build Week13 Friday stage gate input.

This aggregates existing verified evidence only.
It does not regenerate artifacts and does not claim production readiness.
"""

from __future__ import annotations

import argparse
import glob
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def find_key(obj: Any, names: list[str]) -> Any:
    targets = {n.lower() for n in names}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in targets:
                return v
        for v in obj.values():
            found = find_key(v, names)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = find_key(item, names)
            if found is not None:
                return found
    return None


def contains(obj: Any, text: str) -> bool:
    if isinstance(obj, dict):
        return any(contains(k, text) or contains(v, text) for k, v in obj.items())
    if isinstance(obj, list):
        return any(contains(x, text) for x in obj)
    return text in str(obj)


def to_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except Exception:
        return None


def latest_file(base: Path, patterns: list[str]) -> str | None:
    hits: list[Path] = []
    for pat in patterns:
        hits.extend(Path(p) for p in glob.glob(str(base / pat)))
    hits = [p for p in hits if p.is_file()]
    if not hits:
        return None
    return str(max(hits, key=lambda p: p.stat().st_mtime))


def first_present(*values: Any) -> Any:
    for v in values:
        if v is not None:
            return v
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mainbase", required=True)
    ap.add_argument("--java", required=True)
    ap.add_argument("--cloud", required=True)
    ap.add_argument("--out", default="loadtest/reports/week13_friday_stage_gate_input.json")
    args = ap.parse_args()

    mainbase = Path(args.mainbase).expanduser().resolve()
    java = Path(args.java).expanduser().resolve()
    cloud = Path(args.cloud).expanduser().resolve()

    input_paths = {
        "mainbaseFeedback": mainbase / "artifacts/manifests/week13_platform_promotion_feedback_index.json",
        "javaReadinessApiContract": java / "artifacts/manifests/week13_candidate_bank_demo_readiness_api_contract_report.json",
        "cloudPromotionGate": cloud / "loadtest/reports/week13_candidate_bank_platform_promotion_gate.json",
    }

    blockers: list[str] = []
    docs: dict[str, dict[str, Any]] = {}

    for name, path in input_paths.items():
        try:
            docs[name] = read_json(path)
        except Exception as exc:
            blockers.append(f"{name}: cannot read {path}: {exc}")
            docs[name] = {}

    main_doc = docs["mainbaseFeedback"]
    java_doc = docs["javaReadinessApiContract"]
    cloud_doc = docs["cloudPromotionGate"]

    main_status = find_key(main_doc, ["status", "feedbackStatus"])
    main_decision = find_key(main_doc, ["platformPromotionDecision", "promotionDecision", "decision"])

    java_status = find_key(java_doc, ["status", "contractStatus", "apiContractStatus"])
    java_tests_run = to_int(find_key(java_doc, ["testsRun", "testRunCount", "tests"]))
    java_failures = to_int(find_key(java_doc, ["failures", "failureCount"]))
    java_errors = to_int(find_key(java_doc, ["errors", "errorCount"]))

    cloud_status = find_key(cloud_doc, ["status", "gateStatus", "promotionGateStatus"])
    cloud_decision = find_key(cloud_doc, ["promotionDecision", "platformPromotionDecision", "decision"])

    candidate_count = to_int(first_present(
        find_key(java_doc, ["candidateCount", "candidateTotal", "audioCandidateCount"]),
        find_key(cloud_doc, ["candidateCount", "candidateTotal", "audioCandidateCount"]),
        find_key(main_doc, ["candidateCount", "candidateTotal", "audioCandidateCount"]),
    ))

    worker_success_count = to_int(first_present(
        find_key(java_doc, ["workerSuccessCount", "workerSucceededCount", "successfulWorkerCount"]),
        find_key(cloud_doc, ["workerSuccessCount", "workerSucceededCount", "successfulWorkerCount"]),
        find_key(main_doc, ["workerSuccessCount", "workerSucceededCount", "successfulWorkerCount"]),
    ))

    drilldown_ready_count = to_int(first_present(
        find_key(cloud_doc, ["drilldownReadyCount", "readyDrilldownCount"]),
        find_key(java_doc, ["drilldownReadyCount", "readyDrilldownCount"]),
        find_key(main_doc, ["drilldownReadyCount", "readyDrilldownCount"]),
    ))

    negative_target = "procedural_v0_0002" if (
        contains(main_doc, "procedural_v0_0002")
        or contains(java_doc, "procedural_v0_0002")
        or contains(cloud_doc, "procedural_v0_0002")
    ) else None

    if str(main_status).upper() != "PASS":
        blockers.append(f"mainbase status is not PASS: {main_status}")
    if str(main_decision) != "PROMOTE_TO_WEEK13_DEMO_READY":
        blockers.append(f"mainbase decision unexpected: {main_decision}")

    if str(java_status).upper() != "PASS":
        blockers.append(f"java status is not PASS: {java_status}")
    if java_tests_run != 1:
        blockers.append(f"java testsRun expected 1, got {java_tests_run}")
    if java_failures != 0:
        blockers.append(f"java failures expected 0, got {java_failures}")
    if java_errors != 0:
        blockers.append(f"java errors expected 0, got {java_errors}")

    if str(cloud_status).upper() != "PASS":
        blockers.append(f"cloud status is not PASS: {cloud_status}")

    if candidate_count != 10:
        blockers.append(f"candidateCount expected 10, got {candidate_count}")
    if worker_success_count != 10:
        blockers.append(f"workerSuccessCount expected 10, got {worker_success_count}")
    if drilldown_ready_count != 10:
        blockers.append(f"drilldownReadyCount expected 10, got {drilldown_ready_count}")
    if negative_target != "procedural_v0_0002":
        blockers.append("negative regression target procedural_v0_0002 not found")

    status = "PASS" if not blockers else "FAIL"

    report = {
        "schemaVersion": "week13.friday_stage_gate_input.v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "stageGateDecision": "READY_FOR_FRIDAY_STAGE_GATE" if status == "PASS" else "BLOCKED",
        "verifiedScope": {
            "allowedClaims": [
                "Candidate Audio Bank V1 local demo-ready evidence is aggregated.",
                "Positive path and negative regression evidence are both represented.",
                "This report is a Friday stage gate input, not a production readiness declaration."
            ],
            "forbiddenClaims": [
                "semantic audio quality",
                "human audition passed",
                "final mix readiness",
                "production Kubernetes Job",
                "live Grafana import",
                "S3/MinIO/CSI-backed object storage",
                "production SLO"
            ]
        },
        "inputs": {
            k: {
                "path": str(v),
                "exists": v.exists()
            }
            for k, v in input_paths.items()
        },
        "latestCloudPromotionGateCheckerLog": latest_file(
            cloud,
            ["artifacts/logs/week13_candidate_bank_platform_promotion_gate_check_*.log"]
        ),
        "summary": {
            "mainbaseStatus": main_status,
            "mainbasePromotionDecision": main_decision,
            "javaStatus": java_status,
            "javaApiTestsRun": java_tests_run,
            "javaFailures": java_failures,
            "javaErrors": java_errors,
            "cloudStatus": cloud_status,
            "cloudPromotionDecision": cloud_decision,
            "candidateCount": candidate_count,
            "workerSuccessCount": worker_success_count,
            "drilldownReadyCount": drilldown_ready_count,
            "negativeTarget": negative_target
        },
        "blockers": blockers,
        "nextStageEntry": {
            "ifPass": [
                "Record stage gate transition feedback in Mainbase.",
                "Use this report as Week15 Temporal Alignment Eval / human audition rubric / semantic quality evaluation entry input."
            ],
            "ifFail": [
                "Do not modify upstream Mainbase or Java evidence blindly.",
                "Inspect blockers and rerun the focused failing gate only."
            ]
        }
    }

    out = (cloud / args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "output": str(out),
        "status": status,
        "stageGateDecision": report["stageGateDecision"],
        "blockerCount": len(blockers),
        "blockers": blockers
    }, indent=2, ensure_ascii=False))

    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())