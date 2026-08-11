# Ranker release gate

`DATA_BLOCKED` with no model, OOF, recommendation, or completed human review is an expected `HOLD_HUMAN_REVIEW`, not an infrastructure alert.

Investigate alerts in this order: artifact integrity, cross-repository contract drift, invalid promotion, unavailable metric publication, recommendation while blocked, final selection without human review, then release-manifest integrity. Never repair an alert by inventing OOF values, recommendations, human reviews, or `FINAL_SELECTED` state.

High-cardinality evidence such as bundle digests, paths, case IDs, pair IDs, reviewer IDs, and timestamps belongs in JSON reports or event logs, not Prometheus labels.
