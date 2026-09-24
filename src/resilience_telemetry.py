"""
HandWheel: Production Resilience & Circuit Breaker Engine.
Implements bounded retry with exponential backoff, circuit breaker state machine,
and fallback execution handlers.
"""
import time
import math
import random
from typing import Callable, Any, Optional

class CircuitOpenException(Exception):
    """Raised when invocation is rejected due to open circuit."""
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout_sec: float = 10.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = 0.0

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_failure_time >= self.recovery_timeout_sec:
                self.state = "HALF_OPEN"
                return True
            return False
        if self.state == "HALF_OPEN":
            return True
        return False

def resilient_execute(
    func: Callable[[], Any],
    fallback: Optional[Callable[[], Any]] = None,
    max_retries: int = 3,
    base_delay_sec: float = 0.05,
    circuit_breaker: Optional[CircuitBreaker] = None
) -> Any:
    """
    Executes a callable with circuit breaker gating, exponential backoff,
    and graceful fallback degradation.
    """
    if circuit_breaker and not circuit_breaker.can_execute():
        if fallback:
            return fallback()
        raise CircuitOpenException("Circuit is currently OPEN")

    attempts = 0
    last_err = None
    while attempts < max_retries:
        try:
            result = func()
            if circuit_breaker:
                circuit_breaker.record_success()
            return result
        except Exception as e:
            attempts += 1
            last_err = e
            if circuit_breaker:
                circuit_breaker.record_failure()
            if attempts < max_retries:
                delay = base_delay_sec * (2 ** (attempts - 1)) + random.uniform(0.001, 0.01)
                time.sleep(delay)

    if fallback:
        return fallback()
    raise last_err
