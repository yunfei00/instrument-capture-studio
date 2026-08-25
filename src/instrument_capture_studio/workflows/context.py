from dataclasses import dataclass, field

from instrument_capture_studio.core.results import (
    MeasurementResult,
    SpectrumResult,
    WaveformResult,
)


@dataclass
class CaptureContext:
    """一次联合采集任务运行期间共享的数据上下文。"""

    spectrum: SpectrumResult | None = None

    delay: MeasurementResult | None = None

    cycle_count: MeasurementResult | None = None

    waveform: WaveformResult | None = None

    metadata: dict[str, object] = field(
        default_factory=dict
    )

    @property
    def is_complete(self) -> bool:
        """核心采集结果是否全部获得。"""

        return all(
            (
                self.spectrum is not None,
                self.delay is not None,
                self.cycle_count is not None,
                self.waveform is not None,
            )
        )
