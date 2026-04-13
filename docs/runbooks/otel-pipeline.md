# OTel pipeline (Week06 draft)

## Goal
Add the Week06 minimum OpenTelemetry path on top of the existing local observability baseline.

## Chosen route
- Java side: Java agent first
- Collector side: OTLP receiver + batch processor + debug exporter
- Current goal: get at least one trace through the Collector before connecting a richer backend

## Why this route
- Java zero-code instrumentation can start from a Java agent without immediately modifying application code
- Collector config is easier to validate and iterate than jumping straight into a larger backend stack
- It matches the current Week06 scope: minimum trace path first, richer observability later

## Current pipeline
Java app -> OTLP -> OpenTelemetry Collector -> debug exporter

## Ports
- OTLP gRPC: 4317
- OTLP HTTP: 4318
- health_check: 13133

## Validation plan
1. keep the existing Prometheus/Grafana baseline unchanged
2. start the Collector with this config
3. attach Java agent to the Java service
4. trigger one request
5. verify Collector debug output shows at least one trace

## Notes
- This file is a Week06 draft, not the final runbook
- Production-grade exporter/backends are explicitly out of scope for today
