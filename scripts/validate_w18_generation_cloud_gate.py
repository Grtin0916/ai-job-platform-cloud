#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List


EXPECTED_VARIANTS = {
    "naive",
    "naive_rich",
    "dss_global",
    "dss_event_timeline",
    "dss_layer_avoid",
}


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_json(url: str, timeout: float = 5.0) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def validate_manifest(manifest: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    if manifest.get("status") != "ready_for_java_contract":
        errors.append(f"bad_status={manifest.get('status')}")

    if manifest.get("contract_version") != "w18-generation-handoff-v1":
        errors.append(f"bad_contract_version={manifest.get('contract_version')}")

    summary = manifest.get("summary", {})
    expected_summary = {
        "case_count": 6,
        "job_count": 30,
        "generated_count": 30,
        "playlist_item_count": 30,
        "repair_applied_count": 2,
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            errors.append(f"summary_{key}_expected_{expected}_got_{summary.get(key)}")

    cases = manifest.get("cases", [])
    if len(cases) != 6:
        errors.append(f"case_count_expected_6_got_{len(cases)}")

    for case in cases:
        case_id = case.get("case_id", "")
        variants = case.get("variants", [])
        variant_names = {v.get("variant") for v in variants}

        if case.get("variant_count") != 5:
            errors.append(f"{case_id}:variant_count_expected_5_got_{case.get('variant_count')}")
        if case.get("generated_count") != 5:
            errors.append(f"{case_id}:generated_count_expected_5_got_{case.get('generated_count')}")
        if variant_names != EXPECTED_VARIANTS:
            errors.append(f"{case_id}:variant_set_bad={sorted(variant_names)}")
        if not case.get("default_candidate_variant"):
            errors.append(f"{case_id}:missing_default_candidate_variant")
        if not case.get("default_candidate_audio_path"):
            errors.append(f"{case_id}:missing_default_candidate_audio_path")

        for variant in variants:
            if not variant.get("job_id"):
                errors.append(f"{case_id}:{variant.get('variant')}:missing_job_id")
            if not variant.get("selected_audio_path"):
                errors.append(f"{case_id}:{variant.get('variant')}:missing_selected_audio_path")
            if variant.get("artifact_status") not in {"generated_candidate", "repaired_candidate"}:
                errors.append(f"{case_id}:{variant.get('variant')}:bad_artifact_status={variant.get('artifact_status')}")

    return errors


def validate_live_api(base_url: str) -> Dict[str, Any]:
    base = base_url.rstrip("/")
    result: Dict[str, Any] = {
        "base_url": base,
        "checked": True,
        "ok": False,
        "errors": [],
        "responses": {},
    }

    endpoints = {
        "health": f"{base}/api/v1/week18/generation/health",
        "summary": f"{base}/api/v1/week18/generation/summary",
        "cases": f"{base}/api/v1/week18/generation/cases",
        "default_candidates": f"{base}/api/v1/week18/generation/default-candidates",
    }

    for name, url in endpoints.items():
        try:
            result["responses"][name] = fetch_json(url)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            result["errors"].append(f"{name}: {type(exc).__name__}: {exc}")

    if result["errors"]:
        return result

    health = result["responses"]["health"]
    summary = result["responses"]["summary"]
    cases = result["responses"]["cases"]
    defaults = result["responses"]["default_candidates"]

    if health.get("handoffStatus") != "ready_for_java_contract":
        result["errors"].append(f"health_bad_handoffStatus={health.get('handoffStatus')}")
    if health.get("caseCount") != 6:
        result["errors"].append(f"health_caseCount_expected_6_got_{health.get('caseCount')}")
    if health.get("generatedCount") != 30:
        result["errors"].append(f"health_generatedCount_expected_30_got_{health.get('generatedCount')}")
    if summary.get("summary", {}).get("generated_count") != 30:
        result["errors"].append("summary_generated_count_not_30")
    if not isinstance(cases, list) or len(cases) != 6:
        result["errors"].append(f"cases_expected_6_got_{len(cases) if isinstance(cases, list) else type(cases).__name__}")
    if not isinstance(defaults, list) or len(defaults) != 6:
        result["errors"].append(f"default_candidates_expected_6_got_{len(defaults) if isinstance(defaults, list) else type(defaults).__name__}")

    result["ok"] = not result["errors"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="contracts/week18/w18_java_cloud_handoff_manifest_20260706.json")
    parser.add_argument("--schema", default="contracts/week18/w18_java_cloud_handoff_schema_20260706.json")
    parser.add_argument("--out-json", default="artifacts/week18/w18_generation_cloud_gate_20260706.json")
    parser.add_argument("--java-base-url", default="")
    parser.add_argument("--require-live", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    schema_path = Path(args.schema)

    manifest = read_json(manifest_path)
    schema = read_json(schema_path)

    manifest_errors = validate_manifest(manifest)

    live_result = {
        "checked": False,
        "ok": None,
        "errors": [],
        "base_url": args.java_base_url,
    }
    if args.java_base_url:
        live_result = validate_live_api(args.java_base_url)

    live_required_ok = (not args.require_live) or bool(live_result.get("ok"))

    result = {
        "date": "2026-07-06",
        "scope": "w18_generation_cloud_gate",
        "status": "ready_for_cloud_rollout_gate" if not manifest_errors and live_required_ok else "blocked",
        "manifest": str(manifest_path),
        "schema": str(schema_path),
        "contract_version": manifest.get("contract_version"),
        "manifest_summary": manifest.get("summary"),
        "schema_required_top_level_keys": schema.get("required_top_level_keys"),
        "manifest_error_count": len(manifest_errors),
        "manifest_errors": manifest_errors,
        "live_api": live_result,
        "claim_boundary": [
            "This validates Cloud-side contract readiness for the Java W18 API.",
            "It does not deploy Kubernetes resources.",
            "It does not prove production SLO.",
            "Live API check is only enforced when --require-live is used."
        ],
    }

    out = Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ready_for_cloud_rollout_gate" else 2


if __name__ == "__main__":
    raise SystemExit(main())
