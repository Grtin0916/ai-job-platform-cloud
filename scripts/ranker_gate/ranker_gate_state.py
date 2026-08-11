#!/usr/bin/env python3
"""Monotonic multi-axis release decisions for Ranker delivery contracts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


GATE_ORDER = (
    "artifactIntegrityReady",
    "registryReady",
    "observabilityReady",
    "preferenceDataReady",
    "modelAvailable",
    "oofAvailable",
    "recommendationReady",
    "humanGateReady",
    "finalSelectionReady",
    "productionWorkflowVerified",
)


def evaluate(snapshot: dict[str, Any], observability_ready: bool = True) -> dict[str, Any]:
    ranker = snapshot["ranker"]
    integrity = snapshot["artifactIntegrity"]
    gates = {
        "artifactIntegrityReady": bool(integrity["ready"]),
        "registryReady": snapshot["registry"]["versionCount"] > 0,
        "observabilityReady": observability_ready,
        "preferenceDataReady": ranker["reviewRows"] > 0
        and ranker["reviewSubmittedCount"] == ranker["reviewRows"],
        "modelAvailable": bool(ranker["modelPresent"]),
        "oofAvailable": bool(ranker["oofAvailable"]),
        "recommendationReady": ranker["recommendationCount"] > 0,
        "humanGateReady": bool(ranker["humanReviewCompleted"]),
        "finalSelectionReady": ranker["finalSelectedMutationCount"] > 0,
        "productionWorkflowVerified": bool(
            snapshot["claimBoundary"]["productionWorkflowVerified"]
        ),
    }
    if not integrity["ready"] or not integrity["crossRepositoryDigestMatch"]:
        decision = "BLOCK_ARTIFACT_INTEGRITY"
    elif ranker["promotionStatus"] == "DATA_BLOCKED" and ranker["recommendationCount"]:
        decision = "BLOCK_CONTRACT_DRIFT"
    elif ranker["promotionStatus"] == "DATA_BLOCKED" and ranker["modelPresent"]:
        decision = "BLOCK_INVALID_PROMOTION"
    elif not ranker["humanReviewCompleted"] and ranker["finalSelectedMutationCount"]:
        decision = "BLOCK_HUMAN_GATE_VIOLATION"
    elif not gates["humanGateReady"]:
        decision = "HOLD_HUMAN_REVIEW"
    elif all(gates.values()):
        decision = "PROMOTE"
    else:
        decision = "HOLD_UPSTREAM_DEPENDENCY"
    return {
        "gates": gates,
        "gateOrder": list(GATE_ORDER),
        "overallDecision": decision,
        "nextRequiredAction": "Complete blind preference review"
        if decision == "HOLD_HUMAN_REVIEW"
        else "Resolve the blocking contract violation",
        "falsePromotionCount": int(decision == "PROMOTE" and not all(gates.values())),
        "finalSelectedMutationCount": ranker["finalSelectedMutationCount"],
    }


def injected(snapshot: dict[str, Any], scenario: str) -> dict[str, Any]:
    value = deepcopy(snapshot)
    if scenario == "blocked_contains_recommendations":
        value["ranker"]["recommendationCount"] = 12
    elif scenario == "blocked_contains_model":
        value["ranker"]["modelPresent"] = True
    elif scenario == "final_without_human_review":
        value["ranker"]["humanReviewCompleted"] = False
        value["ranker"]["finalSelectedMutationCount"] = 1
    elif scenario == "bundle_digest_mismatch":
        value["artifactIntegrity"]["ready"] = False
        value["artifactIntegrity"]["crossRepositoryDigestMatch"] = False
    else:
        raise ValueError(f"unknown scenario: {scenario}")
    return value
