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
    def acquire_delay_group(self) -> tuple[MeasurementResult, WaveformResult]: ...
    def acquire_cycle_group(self) -> tuple[MeasurementResult, WaveformResult]: ...


@dataclass(frozen=True)
class PairedTrainingSample:
    """One formal logical sample with two spectra and two DSO-X acquisitions."""

    spectrum_ext: SpectrumResult
    spectrum_imm: SpectrumResult
    delay: MeasurementResult
    cycle_count: MeasurementResult
    waveform_delay: WaveformResult
    waveform_cycle: WaveformResult


def acquire_ext_imm_paired_sample(
    spectrum_analyzer: ArmedSpectrumAdapter,
    oscilloscope: DSOXSampleAdapter,
    *,
    fsw_timeout_s: float | None = None,
    cancel_check: CancelCheck | None = None,
) -> PairedTrainingSample:
    """Acquire one formal paired sample in the qualified hardware ordering.

    Order:
      FSW EXT ARM
      -> DSO-X DELAY group (first independent DIGitize; hardware EXT event)
      -> FSW EXT read
      -> DSO-X CYCLE_COUNT group (second independent DIGitize)
      -> FSW IMM acquire.
    """

    spectrum_analyzer.arm_spectrum("EXT")
    delay, waveform_delay = oscilloscope.acquire_delay_group()

    spectrum_ext = spectrum_analyzer.read_armed_spectrum(
        timeout_s=fsw_timeout_s,
        cancel_check=cancel_check,
        trigger_source="EXT",
    )

    cycle_count, waveform_cycle = oscilloscope.acquire_cycle_group()

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
        waveform_delay=waveform_delay,
        waveform_cycle=waveform_cycle,
    )
