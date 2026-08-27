from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from instrument_capture_studio.core.results import (
    MeasurementResult,
    SpectrumResult,
    WaveformResult,
)


CancelCheck = Callable[[], bool]


class ArmedSpectrumAdapter(Protocol):
    def arm_spectrum(self, trigger_source: str = "EXT") -> None: ...

    def read_armed_spectrum(
        self,
        *,
        timeout_s: float | None = None,
        cancel_check: CancelCheck | None = None,
        trigger_source: str = "EXT",
    ) -> SpectrumResult: ...

    def acquire_spectrum_with_trigger(
        self,
        trigger_source: str | None,
        *,
        timeout_s: float | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> SpectrumResult: ...


class DSOXSampleAdapter(Protocol):
    def acquire_delay(self) -> MeasurementResult: ...
    def acquire_cycle_count(self) -> MeasurementResult: ...
    def acquire_waveform(self) -> WaveformResult: ...


@dataclass(frozen=True)
class PairedTrainingSample:
    """One logical training sample: DSO-X + FSW EXT + same-point FSW IMM."""

    spectrum_ext: SpectrumResult
    spectrum_imm: SpectrumResult
    delay: MeasurementResult
    cycle_count: MeasurementResult
    waveform: WaveformResult


def acquire_ext_imm_paired_sample(
    spectrum_analyzer: ArmedSpectrumAdapter,
    oscilloscope: DSOXSampleAdapter,
    *,
    fsw_timeout_s: float | None = None,
    cancel_check: CancelCheck | None = None,
) -> PairedTrainingSample:
    """Acquire one paired sample in the real hardware ordering.

    Order is intentionally strict:
    1. configure/arm FSW with EXT and return immediately;
    2. acquire the DSO-X measurements, allowing the hardware trigger path to
       trigger the already-armed FSW;
    3. wait for/read the FSW EXT trace;
    4. switch only the next FSW acquisition to IMM and capture a paired trace.
    """

    spectrum_analyzer.arm_spectrum("EXT")

    delay = oscilloscope.acquire_delay()
    cycle_count = oscilloscope.acquire_cycle_count()
    waveform = oscilloscope.acquire_waveform()

    spectrum_ext = spectrum_analyzer.read_armed_spectrum(
        timeout_s=fsw_timeout_s,
        cancel_check=cancel_check,
        trigger_source="EXT",
    )
    spectrum_imm = spectrum_analyzer.acquire_spectrum_with_trigger(
        "IMM",
        timeout_s=fsw_timeout_s,
        cancel_check=cancel_check,
    )

    return PairedTrainingSample(
        spectrum_ext=spectrum_ext,
        spectrum_imm=spectrum_imm,
        delay=delay,
        cycle_count=cycle_count,
        waveform=waveform,
    )
