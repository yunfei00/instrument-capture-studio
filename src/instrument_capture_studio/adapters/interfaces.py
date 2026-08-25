from collections.abc import Callable
from abc import abstractmethod

from instrument_capture_studio.adapters.base import InstrumentAdapter
from instrument_capture_studio.core.results import (
    MeasurementResult,
    SpectrumResult,
    WaveformResult,
)


class OscilloscopeAdapter(InstrumentAdapter):
    """示波器在商业采集产品中需要提供的能力。"""

    @abstractmethod
    def acquire_delay(self) -> MeasurementResult:
        """执行 DELAY 测量并返回结果。"""

    @abstractmethod
    def acquire_cycle_count(self) -> MeasurementResult:
        """执行周期/脉冲计数测量并返回结果。"""

    @abstractmethod
    def acquire_waveform(self) -> WaveformResult:
        """读取示波器波形。"""


class SpectrumAnalyzerAdapter(InstrumentAdapter):
    """频谱分析仪在商业采集产品中需要提供的能力。"""

    @abstractmethod
    def acquire_spectrum(
        self,
        *,
        timeout_s: float | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> SpectrumResult:
        """执行一次频谱采集并返回结果。"""
