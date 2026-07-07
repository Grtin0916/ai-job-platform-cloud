# Week18 evaluation cloud gate

This runbook records the offline Cloud aggregation for the Week18 DSS-vs-naive evaluation handoff.

Inputs:

- Mainbase W18 evaluation closure
- Mainbase audio metrics report
- Mainbase DSS-vs-naive pairwise report
- Mainbase DSS-aware selector report
- Mainbase repair-aware selector seed
- Java evaluation handoff API report

Boundary:

- This is dashboard-ready and Prometheus-sample-ready only.
- It does not claim k6 threshold pass.
- It does not claim production SLO.
- It does not claim live Grafana import.
