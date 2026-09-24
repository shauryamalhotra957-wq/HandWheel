"""
HandWheel: Latency & High-Throughput Performance Profiler.
Measures execution times, percentile latencies (p50, p90, p99), and throughput.
"""
import time
from src.resilience_telemetry import resilient_execute, CircuitBreaker

def run_benchmark():
    iterations = 25_000
    cb = CircuitBreaker()
    latencies = []
    
    def mock_computation():
        return sum(i * 2 for i in range(50))
        
    start_total = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter()
        resilient_execute(mock_computation, circuit_breaker=cb)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1e6)
    end_total = time.perf_counter()
    
    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.50)]
    p90 = latencies[int(len(latencies) * 0.90)]
    p99 = latencies[int(len(latencies) * 0.99)]
    elapsed = end_total - start_total
    
    print(f"=== HandWheel Performance Report ===")
    print(f"Total Cycles: {iterations:,}")
    print(f"Throughput:   {iterations / elapsed:,.0f} ops/sec")
    print(f"Latency P50:  {p50:.2f} microseconds")
    print(f"Latency P90:  {p90:.2f} microseconds")
    print(f"Latency P99:  {p99:.2f} microseconds")

if __name__ == '__main__':
    run_benchmark()
