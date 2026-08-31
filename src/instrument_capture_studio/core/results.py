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
    """频谱分析仪 Trace 采集结果。

    普通扫频使用 ``frequencies_hz`` 作为横轴。FSW Zero Span 时频率不再
    是 Trace 横轴，而是测量条件；此时 ``time_s`` 保存 0..Sweep Time 的
    时间轴，同时 ``frequencies_hz`` 仍可保存每点对应的中心频率以兼容旧
    调用方。
    """

    frequencies_hz: list[float]
    amplitudes_dbm: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    time_s: list[float] | None = None

    @property
    def points(self) -> int:
        return len(self.amplitudes_dbm)

    @property
    def axis_kind(self) -> str:
        return "time" if self.time_s is not None else "frequency"
