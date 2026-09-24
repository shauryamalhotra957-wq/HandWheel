import pytest
import time
from src.resilience_telemetry import CircuitBreaker, CircuitOpenException, resilient_execute

def test_circuit_breaker_closed_to_open_transition():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_sec=0.2)
    assert cb.state == "CLOSED"
    assert cb.can_execute() is True
    
    cb.record_failure()
    cb.record_failure()
    assert cb.state == "CLOSED"
    
    cb.record_failure()
    assert cb.state == "OPEN"
    assert cb.can_execute() is False

def test_circuit_breaker_half_open_recovery():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=0.1)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == "OPEN"
    
    time.sleep(0.15)
    assert cb.can_execute() is True
    assert cb.state == "HALF_OPEN"
    
    cb.record_success()
    assert cb.state == "CLOSED"
    assert cb.failure_count == 0

def test_resilient_execute_retry_and_fallback():
    calls = []
    def failing_fn():
        calls.append(1)
        raise ValueError("Simulated network/hardware fault")
        
    def fallback_fn():
        return "SAFE_FALLBACK_RESULT"

    result = resilient_execute(
        failing_fn,
        fallback=fallback_fn,
        max_retries=3,
        base_delay_sec=0.01
    )
    assert result == "SAFE_FALLBACK_RESULT"
    assert len(calls) == 3

def test_resilient_execute_success():
    def successful_fn():
        return {"status": "OK", "model": "HandWheel"}
        
    result = resilient_execute(successful_fn)
    assert result["status"] == "OK"
