"""Frequency sweep plan for repeated combined captures."""

from dataclasses import dataclass
from decimal import Decimal
from math import isfinite


@dataclass(frozen=True)
class FrequencySweepPlan:
    """Finite inclusive frequency sweep with repeated captures at each point."""

    start_hz: float
    stop_hz: float
    step_hz: float
    span_hz: float
    captures_per_frequency: int

    def __post_init__(self) -> None:
        numeric = {
            "start_hz": self.start_hz,
            "stop_hz": self.stop_hz,
            "step_hz": self.step_hz,
            "span_hz": self.span_hz,
        }
        for name, value in numeric.items():
            if not isfinite(float(value)):
                raise ValueError(f"{name} must be finite")

        if self.start_hz < 0:
            raise ValueError("start_hz must not be negative")
        if self.stop_hz < self.start_hz:
            raise ValueError("stop_hz must be greater than or equal to start_hz")
        if self.step_hz <= 0:
            raise ValueError("step_hz must be greater than 0")
        if self.span_hz < 0:
            raise ValueError("span_hz must not be negative")
        if self.captures_per_frequency < 1:
            raise ValueError("captures_per_frequency must be at least 1")

    @property
    def frequencies_hz(self) -> tuple[float, ...]:
        start = Decimal(str(self.start_hz))
        stop = Decimal(str(self.stop_hz))
        step = Decimal(str(self.step_hz))

        values: list[float] = []
        current = start
        while current <= stop:
            values.append(float(current))
            current += step
        return tuple(values)

    @property
    def frequency_count(self) -> int:
        return len(self.frequencies_hz)

    @property
    def total_captures(self) -> int:
        return self.frequency_count * self.captures_per_frequency
