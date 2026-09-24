"""
Steering Non-Linear Response Curve & Deadzone Processor.
Transforms raw optical hand angle deltas into progressive polynomial steering input
with anti-jitter deadzones for realistic driving telemetry.
"""

class SteeringCurveMapper:
    def __init__(self, deadzone: float = 0.05, exponent: float = 2.2, max_output: float = 1.0):
        self.deadzone = deadzone
        self.exponent = exponent
        self.max_output = max_output

    def map_input(self, raw_input: float) -> float:
        """
        Maps raw input in range [-1.0, 1.0] to curved output.
        """
        clamped = max(-1.0, min(1.0, raw_input))
        sign = 1.0 if clamped >= 0 else -1.0
        mag = abs(clamped)

        if mag <= self.deadzone:
            return 0.0

        # Rescale remaining interval [deadzone, 1.0] to [0.0, 1.0]
        normalized_mag = (mag - self.deadzone) / (1.0 - self.deadzone)
        curved_mag = (normalized_mag ** self.exponent) * self.max_output
        return round(sign * curved_mag, 4)
