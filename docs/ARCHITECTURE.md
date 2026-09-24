# HandWheel: System Architecture & Technical Topology

MediaPipe hand tracking geometry mapped to virtual analog XInput steering axis with predictive Kalman smoothing.

## 1. System Topology & Pipeline Flow

```mermaid
flowchart TD
    subgraph Ingestion["Ingestion & Boundary Layer"]
        InputSource["Raw Input Stream / Files"]
        Sanitizer["Boundary Validator & Integrity Check"]
    end

    subgraph CoreEngine["Core Computational Engine"]
        Preprocessor["Feature Normalization & Preprocessing"]
        ModelCore["Inference / Decision Pipeline (Webcam Hand Tracking to Virtual Xbox Steering Wheel)"]
        SafetyGate["Resilience & Anomaly Guard"]
    end

    subgraph Delivery["Delivery & Observability"]
        OutputSink["Formatted Output / Actions"]
        Telemetry["Metrics Ledger & Health Diagnostics"]
    end

    InputSource --> Sanitizer
    Sanitizer --> Preprocessor
    Preprocessor --> ModelCore
    ModelCore --> SafetyGate
    SafetyGate --> OutputSink
    SafetyGate -.-> Telemetry
```

## 2. Execution Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Client as Ingestion Client
    participant Engine as HandWheel Core
    participant Guard as Resilience Guard
    participant Sink as Sink / Caller

    Client->>Engine: Process Payload / Batch
    Engine->>Guard: Validate Bounds & Circuit State
    alt Circuit Open or Degraded
        Guard-->>Engine: Trigger Fast-Fallback Recovery
        Engine-->>Client: Fallback Response with Health Warning
    else Circuit Closed (Healthy)
        Engine->>Engine: Execute Core Inference / Computation
        Engine->>Guard: Report Success & Latency
        Engine-->>Sink: Emit High-Precision Result
    end
```

## 3. Resilience Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> Closed
    Closed --> Degraded: Latency Spike or Single Failure
    Degraded --> Closed: Success Recovery
    Degraded --> Open: Error Threshold Exceeded (5 Consecutive)
    Open --> HalfOpen: Recovery Timeout Elapsed (30s)
    HalfOpen --> Closed: Probe Request Successful
    HalfOpen --> Open: Probe Request Failed
```

## 4. Architectural Design Principles
- **Predictable Latency**: All computational critical paths avoid unbounded loops or uncontrolled blocking IO.
- **Fail-Safe Degradation**: If underlying model components or system drivers encounter unexpected exceptions, the system transitions gracefully rather than causing process abortion.
