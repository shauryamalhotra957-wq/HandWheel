# HandWheel: Production Operations Runbook & Incident Triage

Production guidance, operational SLOs, and incident playbooks for **Webcam Hand Tracking to Virtual Xbox Steering Wheel**.

## Service Level Objectives (SLOs)
- **Inference Availability**: >= 99.9% uptime during operational shifts.
- **Latency Budget (P95)**: < 120ms roundtrip processing latency.
- **Circuit Breaker Trip Threshold**: 5 consecutive errors over a 10-second sliding window.

## Incident Triage Playbooks

### Sev-1: Model Outage / Unhandled Processing Exception
1. **Detection**: Sustained error rate > 5% over 2 consecutive minutes.
2. **Immediate Action**: Engage fallback handler; redirect critical ingestion streams to standby replica.
3. **Investigation**: Inspect application logs for out-of-memory (OOM) faults or corrupt incoming payloads.
4. **Resolution**: Restart container instance with clean cache and verify health status via `/livez` probe.

### Sev-2: Latency Degradation / Queue Backpressure
1. **Detection**: P99 latency exceeding 500ms for more than 5 minutes.
2. **Remediation**: Scale worker concurrency or reduce batch size until queue drain rate exceeds arrival rate.
