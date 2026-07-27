#!/usr/bin/env python3
"""Verify W19 observability values, dashboard, and safe alert semantics."""
import argparse, json, re
from pathlib import Path
def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def main():
    p=argparse.ArgumentParser()
    for x in ("observability","summary","metrics","dashboard","rules"): p.add_argument("--"+x, required=True)
    a=p.parse_args(); o,s,d=load(a.observability),load(a.summary),load(a.dashboard)
    assert (s["records"],s["manualReview"],s["rejected"],s["finalSelected"]) == (20,18,2,0)
    assert (s["artifactReferences"],s["artifactUniqueBlobs"],s["integrityFailures"]) == (40,34,0)
    assert o["ratios"]["meanOnsetGainMs"]["available"] is False
    assert len(d["panels"]) >= 10 and d["uid"] == "repair-release-w19"
    text=Path(a.metrics).read_text(); rules=Path(a.rules).read_text()
    required=["repair_records","repair_proxy_improved_records","repair_manual_review_pending",
              "repair_final_selected_records","repair_artifact_integrity_failures","repair_demo_pack_verified"]
    assert all(re.search(rf"(?m)^{x} [0-9]+$",text) for x in required)
    assert not any(x in text for x in ("repair_id=", "sha256=", "path="))
    assert "NoFinalSelectedAlert" not in rules
    assert all(x in rules for x in ("RepairArtifactIntegrityFailure","RepairSourceInconsistency",
                                    "RepairReviewQueueStalled","RepairDemoPackBroken"))
    assert all(s[x] is False for x in ("liveGrafanaImportVerified","productionPrometheusVerified",
                                       "alertmanagerConfigured","productionAlertingVerified"))
    print(json.dumps({"verified":True,"panels":len(d["panels"]),"records":20,"integrityFailures":0}))
if __name__=="__main__": main()
