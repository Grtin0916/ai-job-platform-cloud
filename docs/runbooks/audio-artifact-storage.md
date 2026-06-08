# Week13 Audio Artifact Storage Runbook

## Scope

This runbook records local Docker Desktop / kind storage semantics for Week13 audio artifact evidence.

Generated from:

- Mainbase dry-run manifest: `/home/GRT/work/audio_engineering_repo_skeleton_v1/artifacts/audio_mix/week13_mix_preview_manifest.json`
- Mainbase placement table: `/home/GRT/work/audio_engineering_repo_skeleton_v1/artifacts/evals/week13_mix_global_placement_table.csv`
- Java registry report: `/home/GRT/work/media-task-platform-java/artifacts/manifests/week13_java_audio_artifact_registry_contract_report.json`

## Runtime context

- Docker runtime: Docker Desktop
- Local object root: `/var/local/audio-artifacts/week13`
- Pod mount root: `/mnt/audio-artifacts/week13`
- Storage mode: local object directory / hostPath / local PV simulation

## Placement rule

- `full_clip`: global timeline starts at `0`
- `event_local`: global timeline starts at `expectedStartSec`

## Current metrics

- candidateCount: 10
- fullClipCount: 5
- eventLocalCount: 5
- placementRequiredCount: 5
- fixedPlacementMisplacedCount: 0
- naiveZeroWouldMisplaceCount: 5

## Cleanup policy

Week13 local object copies are safe to delete only after the storage index, dashboard stub, and weekly summary are committed.

## Boundary

This is not production object storage, not a durable registry, not CSI production storage, not final mixer readiness, not semantic quality validation, not human audition, and not production SLO.
