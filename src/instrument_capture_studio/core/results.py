from dataclasses import dataclass, field
from typing import Any


@dataclass
class MeasurementResult:
    """单个测量值结果，例如 DELAY 或周期计数。"""

    measurement: str
    value: float
    unit: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WaveformResult:
    """示波器波形采集结果。"""

    channel: str
    time_s: list[float]
    voltage_v: list[float]
    sample_rate_hz: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def points(self) -> int:
        return len(self.voltage_v)


@dataclass
class SpectrumResult:
    """频谱分析仪 Trace 采集结果。"""

    frequencies_hz: list[float]
    amplitudes_dbm: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def points(self) -> int:
        return len(self.amplitudes_dbm)
