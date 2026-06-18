#!/usr/bin/env python3
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

GATE = Path("loadtest/reports/week15_temporal_alignment_eval_v1_gate.json")
OUT = Path("loadtest/reports/week15_temporal_alignment_eval_v1_risk_taxonomy.json")
PROM = Path("observability/prometheus/week15_temporal_alignment_eval_v1_risk_taxonomy_metrics.prom")

CID_RE = re.compile(r"procedural_v0_\d+")

CLASS_PATTERNS = [
    ("remediation_or_drift", re.compile(r"remediat|trimmed|preroll|fail_drift|drift|onsetdelta|delta", re.I)),
    ("review_required_or_blocked", re.compile(r"review|required|blocked|human|partial|manual", re.I)),
    ("signal_proxy", re.compile(r"signal|rms|zcr|low.energy|energy|proxy|near_miss|warn", re.I)),
]

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def walk(obj, path="$"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, obj

def classify_context(text):
    hits = []
    for name, pat in CLASS_PATTERNS:
        if pat.search(text):
            hits.append(name)
    return hits or ["mentioned_only"]

def safe_label(s):
    return re.sub(r"[^a-zA-Z0-9_:\-.]", "_", str(s))[:160]

gate = load_json(GATE)
source_reports = gate.get("sourceReports") or {}

candidate_evidence = defaultdict(list)

for source_name, meta in source_reports.items():
    p = Path(meta.get("path") or "")
    if not p.exists() or p == GATE:
        continue

    raw = p.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except Exception:
        data = raw

    for path, value in walk(data):
        text = f"{path} {value}"
        ids = CID_RE.findall(text)
        if not ids:
            continue
        classes = classify_context(text)
        snippet = str(value)
        if len(snippet) > 240:
            snippet = snippet[:240] + "..."
        for cid in sorted(set(ids)):
            candidate_evidence[cid].append({
                "source": source_name,
                "sourcePath": str(p),
                "jsonPath": path,
                "classes": classes,
                "snippet": snippet
            })

# 保底：gate riskCandidateIds 中出现但 source path 没定位到的，不能消失。
for cid in gate.get("riskCandidateIds") or []:
    if cid not in candidate_evidence:
        candidate_evidence[cid].append({
            "source": "evalV1Gate",
            "sourcePath": str(GATE),
            "jsonPath": "$.riskCandidateIds",
            "classes": ["gate_proxy_risk"],
            "snippet": "candidate appears in eval v1 gate riskCandidateIds"
        })

candidate_rows = []
class_counts = defaultdict(int)

for cid in sorted(candidate_evidence):
    evidences = candidate_evidence[cid]
    classes = sorted(set(c for e in evidences for c in e["classes"]))
    primary = "mentioned_only"
    for preferred in ["remediation_or_drift", "review_required_or_blocked", "signal_proxy", "gate_proxy_risk"]:
        if preferred in classes:
            primary = preferred
            break
    class_counts[primary] += 1
    candidate_rows.append({
        "candidateId": cid,
        "primaryRiskClass": primary,
        "riskClasses": classes,
        "evidenceCount": len(evidences),
        "evidence": evidences[:8]
    })

decision = "PASS" if candidate_rows else "FAIL"

report = {
    "schemaVersion": "week15.temporal_alignment.eval_v1_risk_taxonomy.v1",
    "generatedAt": datetime.now(timezone.utc).isoformat(),
    "scope": "offline repository evidence taxonomy; not human-review pass/fail",
    "decision": decision,
    "sourceGate": str(GATE),
    "gateDecision": gate.get("gateDecision"),
    "candidateRiskTotal": len(candidate_rows),
    "riskClassCounts": dict(sorted(class_counts.items())),
    "candidates": candidate_rows,
    "blockedClaimsPreserved": gate.get("blockedClaims"),
    "nextAction": (
        "Use taxonomy classes as dashboard dimensions or refine source reports to emit explicit risk fields."
        if decision == "PASS"
        else "Fix missing candidate evidence extraction before dashboard consumption."
    )
}

OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

lines = [
    "# HELP week15_temporal_alignment_eval_v1_risk_candidate_by_class Candidate risk count by taxonomy class.",
    "# TYPE week15_temporal_alignment_eval_v1_risk_candidate_by_class gauge",
]
for cls, count in sorted(class_counts.items()):
    lines.append(f'week15_temporal_alignment_eval_v1_risk_candidate_by_class{{risk_class="{safe_label(cls)}"}} {count}')

lines += [
    "# HELP week15_temporal_alignment_eval_v1_risk_taxonomy_pass Risk taxonomy generation pass flag.",
    "# TYPE week15_temporal_alignment_eval_v1_risk_taxonomy_pass gauge",
    f"week15_temporal_alignment_eval_v1_risk_taxonomy_pass {1 if decision == 'PASS' else 0}",
]

PROM.write_text("\n".join(lines) + "\n", encoding="utf-8")

print(json.dumps({
    "decision": decision,
    "candidateRiskTotal": len(candidate_rows),
    "riskClassCounts": dict(sorted(class_counts.items())),
    "out": str(OUT),
    "prom": str(PROM)
}, indent=2, ensure_ascii=False))

if decision != "PASS":
    raise SystemExit("RISK_TAXONOMY_FAIL")
