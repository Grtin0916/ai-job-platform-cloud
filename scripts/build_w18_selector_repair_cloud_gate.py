#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def prom_escape(s: str) -> str:
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", required=True)
    ap.add_argument("--out-gate", required=True)
    ap.add_argument("--out-prom", required=True)
    ap.add_argument("--out-dashboard", required=True)
    ap.add_argument("--out-summary", required=True)
    args = ap.parse_args()

    contract_path = Path(args.contract)
    contract = read_json(contract_path)
    summary = contract.get("summary", {})

    winner_count = int(summary.get("winner_count", 0))
    failure_count = int(summary.get("failure_count", 0))
    repair_probe_count = int(summary.get("repair_probe_count", 0))
    proxy_improved_count = int(summary.get("proxy_improved_count", 0))
    missing_asset_count = int(summary.get("missing_asset_count", 999))
    boundary = contract.get("boundary", "")

    repaired = contract.get("repaired_candidates", [])
    winners = contract.get("winners", [])

    category_counts = summary.get("failure_category_counts", {})
    action_counts = summary.get("repair_action_counts", {})

    checks = {
        "contract_file_exists": contract_path.exists(),
        "contract_name_ok": contract.get("contract_name") == "week18_selector_repair_handoff",
        "producer_mainbase": contract.get("producer") == "mainbase",
        "cloud_listed_as_consumer": "cloud" in contract.get("intended_consumers", []),
        "winner_count_eq_6": winner_count == 6,
        "repair_probe_count_eq_6": repair_probe_count == 6,
        "proxy_improved_count_ge_2": proxy_improved_count >= 2,
        "missing_asset_count_eq_0": missing_asset_count == 0,
        "boundary_present": bool(boundary),
        "not_claiming_production_slo": "production SLO" in boundary,
        "not_claiming_full_repair_engine": "full repair engine" in boundary,
    }

    status = "PASS" if all(checks.values()) else "FAIL"

    gate = {
        "gate_name": "w18_selector_repair_cloud_gate",
        "gate_version": "2026-07-08.v1",
        "status": status,
        "input_contract": str(contract_path),
        "checks": checks,
        "summary": {
            "winner_count": winner_count,
            "failure_count": failure_count,
            "repair_probe_count": repair_probe_count,
            "proxy_improved_count": proxy_improved_count,
            "missing_asset_count": missing_asset_count,
            "failure_category_counts": category_counts,
            "repair_action_counts": action_counts,
        },
        "samples": {
            "winner_cases": winners[:3],
            "repair_candidates": repaired[:3],
        },
        "boundary": boundary,
        "claim_boundary": (
            "Offline Cloud aggregation only. This is dashboard-ready evidence, "
            "not k6 threshold pass, not live Grafana import, and not production SLO."
        ),
    }

    write_json(Path(args.out_gate), gate)

    prom_lines = [
        "# HELP w18_selector_repair_gate_status 1 if the offline selector repair cloud gate passes.",
        "# TYPE w18_selector_repair_gate_status gauge",
        f'w18_selector_repair_gate_status{{gate_version="2026-07-08.v1"}} {1 if status == "PASS" else 0}',
        "# HELP w18_selector_repair_winner_count Number of selector v2 winners.",
        "# TYPE w18_selector_repair_winner_count gauge",
        f'w18_selector_repair_winner_count{{source="mainbase_contract"}} {winner_count}',
        "# HELP w18_selector_repair_probe_count Number of micro repair probes.",
        "# TYPE w18_selector_repair_probe_count gauge",
        f'w18_selector_repair_probe_count{{source="mainbase_contract"}} {repair_probe_count}',
        "# HELP w18_selector_repair_proxy_improved_count Number of repair probes improved by proxy metrics.",
        "# TYPE w18_selector_repair_proxy_improved_count gauge",
        f'w18_selector_repair_proxy_improved_count{{source="mainbase_contract"}} {proxy_improved_count}',
        "# HELP w18_selector_repair_missing_asset_count Missing asset count reported by contract.",
        "# TYPE w18_selector_repair_missing_asset_count gauge",
        f'w18_selector_repair_missing_asset_count{{source="mainbase_contract"}} {missing_asset_count}',
    ]

    for cat, count in sorted(category_counts.items()):
        prom_lines.append(
            f'w18_selector_repair_failure_category_count{{category="{prom_escape(cat)}"}} {int(count)}'
        )
    for action, count in sorted(action_counts.items()):
        prom_lines.append(
            f'w18_selector_repair_action_count{{action="{prom_escape(action)}"}} {int(count)}'
        )

    out_prom = Path(args.out_prom)
    out_prom.parent.mkdir(parents=True, exist_ok=True)
    out_prom.write_text("\n".join(prom_lines) + "\n", encoding="utf-8")

    dashboard = {
        "title": "W18 Selector Repair Dashboard Seed",
        "schemaVersion": 1,
        "tags": ["week18", "selector", "repair", "offline-gate"],
        "boundary": gate["claim_boundary"],
        "panels": [
            {"title": "Gate Status", "metric": "w18_selector_repair_gate_status", "expected": 1},
            {"title": "Selector Winners", "metric": "w18_selector_repair_winner_count", "expected": 6},
            {"title": "Repair Probes", "metric": "w18_selector_repair_probe_count", "expected": 6},
            {"title": "Proxy Improved", "metric": "w18_selector_repair_proxy_improved_count", "expected_min": 2},
            {"title": "Missing Assets", "metric": "w18_selector_repair_missing_asset_count", "expected": 0},
            {"title": "Failure Categories", "metric": "w18_selector_repair_failure_category_count"},
            {"title": "Repair Actions", "metric": "w18_selector_repair_action_count"},
        ],
        "source_files": {
            "contract": str(contract_path),
            "gate": args.out_gate,
            "prometheus_sample": args.out_prom,
        },
    }

    write_json(Path(args.out_dashboard), dashboard)

    out_summary = {
        "task": "build_w18_selector_repair_cloud_gate",
        "status": status,
        "winner_count": winner_count,
        "failure_count": failure_count,
        "repair_probe_count": repair_probe_count,
        "proxy_improved_count": proxy_improved_count,
        "missing_asset_count": missing_asset_count,
        "panel_count": len(dashboard["panels"]),
        "checks": checks,
        "outputs": {
            "gate": args.out_gate,
            "prometheus": args.out_prom,
            "dashboard": args.out_dashboard,
            "summary": args.out_summary,
        },
        "boundary": gate["claim_boundary"],
    }

    write_json(Path(args.out_summary), out_summary)
    print(json.dumps(out_summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
