from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from instrument_capture_studio.core.results import SpectrumResult, WaveformResult


CancelCheck = Callable[[], bool]


class ArmedSpectrumAdapter(Protocol):
    def read_sweep_time_s(self) -> float: ...
    def arm_external_current_setup(self) -> None: ...

    def read_armed_spectrum(
        self,
        *,
        timeout_s: float | None = None,
        cancel_check: CancelCheck | None = None,
        trigger_source: str = "EXT",
    ) -> SpectrumResult: ...

    def acquire_freerun_current_setup(
        self,
        *,
        timeout_s: float | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> SpectrumResult: ...


class DSOXSampleAdapter(Protocol):
    def configure_sync_window(self, sweep_time_s: float) -> dict[str, object]: ...
    def acquire_sync_waveform(
        self,
        *,
        cancel_check: CancelCheck | None = None,
    ) -> WaveformResult: ...
    def configure_followup_window(self) -> dict[str, object]: ...
    def acquire_followup_waveform(
        self,
        *,
        cancel_check: CancelCheck | None = None,
    ) -> WaveformResult: ...


@dataclass(frozen=True)
class PairedTrainingSample:
    """One final logical sample with two spectra and two Single scope waveforms."""

    sweep_time_s: float
    spectrum_ext: SpectrumResult
    waveform_sync: WaveformResult
    waveform_followup: WaveformResult
    spectrum_freerun: SpectrumResult
    sync_window: dict[str, object]
    followup_window: dict[str, object]


def acquire_ext_imm_paired_sample(
    spectrum_analyzer: ArmedSpectrumAdapter,
    oscilloscope: DSOXSampleAdapter,
    *,
    fsw_timeout_s: float | None = None,
    cancel_check: CancelCheck | None = None,
) -> PairedTrainingSample:
    """Acquire one final paired sample; all four physical acquisitions are Single."""

    sweep_time_s = spectrum_analyzer.read_sweep_time_s()
    sync_window = oscilloscope.configure_sync_window(sweep_time_s)
    spectrum_analyzer.arm_external_current_setup()
    waveform_sync = oscilloscope.acquire_sync_waveform(cancel_check=cancel_check)

    spectrum_ext = spectrum_analyzer.read_armed_spectrum(
        timeout_s=fsw_timeout_s,
        cancel_check=cancel_check,
        trigger_source="EXT",
    )

    followup_window = oscilloscope.configure_followup_window()
    waveform_followup = oscilloscope.acquire_followup_waveform(
        cancel_check=cancel_check,
    )
    spectrum_freerun = spectrum_analyzer.acquire_freerun_current_setup(
        timeout_s=fsw_timeout_s,
        cancel_check=cancel_check,
    )

    return PairedTrainingSample(
        sweep_time_s=sweep_time_s,
        spectrum_ext=spectrum_ext,
        waveform_sync=waveform_sync,
        waveform_followup=waveform_followup,
        spectrum_freerun=spectrum_freerun,
        sync_window=sync_window,
        followup_window=followup_window,
    )
