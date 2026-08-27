from dataclasses import dataclass, field

from instrument_capture_studio.core.results import (
    MeasurementResult,
    SpectrumResult,
    WaveformResult,
)


@dataclass
class CaptureContext:
    """一次采集任务运行期间共享的数据上下文。

    ``spectrum`` is the schema-v1 single-spectrum field.
    ``spectrum_ext`` / ``spectrum_imm`` are schema-v2 paired-training fields.
    Keeping all three fields allows old jobs to remain loadable while new
    recipes can persist the real EXT + IMM training pair explicitly.
    """

    spectrum: SpectrumResult | None = None
    spectrum_ext: SpectrumResult | None = None
    spectrum_imm: SpectrumResult | None = None

    delay: MeasurementResult | None = None
    cycle_count: MeasurementResult | None = None
    waveform: WaveformResult | None = None

    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def schema_version(self) -> int:
        return 2 if (self.spectrum_ext is not None or self.spectrum_imm is not None) else 1

    @property
    def is_complete(self) -> bool:
        """Legacy schema-v1 combined capture completeness."""
        return all(
            (
                self.spectrum is not None,
                self.delay is not None,
                self.cycle_count is not None,
                self.waveform is not None,
            )
        )

    @property
    def is_paired_complete(self) -> bool:
        """Schema-v2 EXT + IMM + DSO-X logical sample completeness."""
        return all(
            (
                self.spectrum_ext is not None,
                self.spectrum_imm is not None,
                self.delay is not None,
                self.cycle_count is not None,
                self.waveform is not None,
            )
        )

    @property
    def capture_complete(self) -> bool:
        return self.is_paired_complete if self.schema_version == 2 else self.is_complete
