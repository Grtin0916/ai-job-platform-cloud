# W20 durable demo job gate

This gate promotes Java-owned SHA-256 blobs into a local Cloud object boundary,
imports the real Java jobs into SQLite, exercises lease takeover and fencing,
then builds a twelve-card release.

Run `python3 -m unittest discover -s tests/demo_gate -p 'test_*.py' -v` before
rebuilding artifacts. The generated release may be `GATE_FAILED` when the real
k6 runtime is unavailable; never edit its exit record into a pass.

The current contract contains ten `PROVISIONAL_SELECTED` cases, two
blocked/rejected cases, and no final selection. A successful Java process proves
execution and digest integrity only. Human review, production object storage,
multi-node consensus, distributed exactly-once behavior, live Grafana import,
production Prometheus/Alertmanager, SLSA attestation, and GitHub-built release
remain unverified.

Recovery order:

1. Stop if the Java handoff is not 12/10/2/0.
2. Stop promotion on any missing blob or SHA mismatch.
3. Treat a repeated import digest as reuse; reject a changed digest for an
   existing Java job.
4. Use `BEGIN IMMEDIATE` for lease acquisition. A takeover increments the
   fencing token, and an older token must never finalize.
5. Preserve the real k6 exit code. A failed or blocked gate still produces an
   inspectable release marked `GATE_FAILED`.
6. Verify ZIP CRC, member equality, checksums, playable count, and host-path
   absence before handoff.
