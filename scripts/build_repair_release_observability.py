#!/usr/bin/env python3
"""Build the W19 repair decision-funnel observability release."""
import argparse, hashlib, json
from collections import Counter
from pathlib import Path

def load(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def dump(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mainbase-root", required=True); p.add_argument("--java-root", required=True)
    p.add_argument("--out-json", required=True); p.add_argument("--out-summary", required=True)
    p.add_argument("--out-prom", required=True); p.add_argument("--demo-verify")
    a = p.parse_args()
    mb, java = Path(a.mainbase_root).resolve(), Path(a.java_root).resolve()
    workflow_path = java/"artifacts/manifests/repair_workflow_report_20260716.json"
    index_path = java/"artifacts/manifests/repair_artifact_index_20260716.json"
    semantic_path = mb/"reports/layer_semantic_repair_summary_20260715.json"
    workflow, index, semantic = load(workflow_path), load(index_path), load(semantic_path)
    records, artifacts = workflow["records"], index["artifacts"]
    failures = []
    for item in artifacts:
        path = java/item["materializedPath"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual != item["sha256"]: failures.append(item["materializedPath"])
    decisions = Counter(x["repairDecision"] for x in records)
    actions = Counter(x["repairAction"] for x in records)
    sources = Counter(x["sourceMode"] for x in records)
    proxy = semantic["mixedOnlyProxyImprovedCount"]
    requested = workflow["summary"]["manualReviewRequestedCount"]
    completed = workflow["summary"]["manualReviewCompletedCount"]
    pending = workflow["summary"]["manualReviewPendingCount"]
    final = workflow["summary"]["finalSelectedCount"]
    rejected = decisions["REPAIR_REJECTED"]
    demo_verified = False
    if a.demo_verify and Path(a.demo_verify).is_file():
        demo_verified = bool(load(a.demo_verify).get("verified"))
    ratios = {
        "proxyImprovementRatio": {"numerator": proxy, "denominator": len(records), "available": True, "value": proxy/len(records)},
        "manualReviewCompletionRatio": {"numerator": completed, "denominator": requested, "available": requested > 0,
                                        "value": completed/requested if requested else None},
        "finalSelectionRatio": {"numerator": final, "denominator": len(records), "available": True, "value": final/len(records)},
        "meanOnsetGainMs": {"numerator": None, "denominator": 0, "available": False, "value": None},
    }
    boundary = {
        "grafanaDashboardJsonValidated": True, "grafanaProvisioningConfigValidated": True,
        "liveGrafanaImportVerified": False, "productionPrometheusVerified": False,
        "alertmanagerConfigured": False, "productionAlertingVerified": False,
    }
    result = {
        "schemaVersion": "repair-observability/v1", "sourceCommit": workflow["sourceCommit"],
        "inputs": [str(workflow_path), str(index_path), str(semantic_path)],
        "acousticEvidence": {"recordCount": len(records), "proxyImprovedCount": proxy,
                             "onsetSampleCount": 0, "onsetMetricAvailable": False,
                             "repairActionCounts": dict(sorted(actions.items())), "sourceModeCounts": dict(sorted(sources.items()))},
        "workflowDecision": {"decisionCounts": dict(sorted(decisions.items())), "manualReviewRequestedCount": requested,
                             "manualReviewCompletedCount": completed, "manualReviewPendingCount": pending,
                             "finalSelectedCount": final, "rejectedCount": rejected},
        "artifactIntegrity": {"referenceCount": len(artifacts), "uniqueBlobCount": len({x["sha256"] for x in artifacts}),
                              "integrityFailureCount": len(failures), "failures": failures},
        "sourceConsistency": workflow["sourceCommit"] == index["sourceCommit"],
        "ratios": ratios, "demoPackVerified": demo_verified, "boundaries": boundary,
        "releaseReadiness": {"finalSelectionReady": final > 0 and completed > 0,
                             "demoReleaseReady": demo_verified and not failures}
    }
    summary = {
        "records": len(records), "manualReview": decisions["MANUAL_REVIEW"], "rejected": rejected,
        "finalSelected": final, "artifactReferences": len(artifacts),
        "artifactUniqueBlobs": len({x["sha256"] for x in artifacts}), "integrityFailures": len(failures),
        "onsetMetricAvailable": False, "demoPackVerified": demo_verified,
        "finalSelectionReady": False, **boundary
    }
    dump(a.out_json, result); dump(a.out_summary, summary)
    metrics = {
        "repair_records": len(records), "repair_proxy_improved_records": proxy,
        "repair_manual_review_pending": pending, "repair_manual_review_requested": requested,
        "repair_manual_review_completed": completed, "repair_final_selected_records": final,
        "repair_rejected_records": rejected, "repair_artifact_references": len(artifacts),
        "repair_artifact_unique_blobs": len({x["sha256"] for x in artifacts}),
        "repair_artifact_integrity_failures": len(failures),
        "repair_source_consistency": int(result["sourceConsistency"]),
        "repair_onset_sample_count": 0,
        "repair_demo_pack_build_attempted": int(a.demo_verify is not None),
        "repair_demo_pack_verified": int(demo_verified),
    }
    lines = []
    for name, value in metrics.items():
        lines += [f"# HELP {name} W19 repair release metric.", f"# TYPE {name} gauge", f"{name} {value}"]
    Path(a.out_prom).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out_prom).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
if __name__ == "__main__": main()
