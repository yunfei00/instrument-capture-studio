from dataclasses import dataclass, field

from instrument_capture_studio.core.results import (
    MeasurementResult,
    SpectrumResult,
    WaveformResult,
)


@dataclass
class CaptureContext:
    """Shared data collected during one logical Capture Job.

    The final paired recipe keeps the original four primary traces:

    - ``spectrum_ext``: FSW spectrum triggered by the first DSO-X acquisition.
    - ``waveform_sync``: DSO-X waveform from that same synchronization event.
    - ``waveform_followup``: a second independent DSO-X waveform after applying
      the operator-configurable follow-up Position/Scale window.
    - ``spectrum_freerun``: final FSW Free Run / IMM spectrum.

    ``spectrum_video`` is an optional fifth FSW trace appended after those four.
    It deliberately does not change the original paired-completeness contract,
    so disabling the option leaves the qualified v1.2 acquisition unchanged.

    Legacy fields remain only for the standalone DSO-X recipe and internal
    regression plumbing. They are not part of the primary paired data contract.
    """

    spectrum: SpectrumResult | None = None
    spectrum_ext: SpectrumResult | None = None
    spectrum_freerun: SpectrumResult | None = None
    spectrum_video: SpectrumResult | None = None
    spectrum_imm: SpectrumResult | None = None

    waveform: WaveformResult | None = None
    waveform_sync: WaveformResult | None = None
    waveform_followup: WaveformResult | None = None

    # Standalone DSO-X legacy recipe fields.
    delay: MeasurementResult | None = None
    cycle_count: MeasurementResult | None = None
    waveform_delay: WaveformResult | None = None
    waveform_cycle: WaveformResult | None = None

    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def schema_version(self) -> int:
        return 1

    @property
    def is_complete(self) -> bool:
        """Legacy internal combined-workflow completeness."""
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
        """Original synchronized paired-sample completeness (four primary traces)."""
        return all(
            (
                self.spectrum_ext is not None,
                self.waveform_sync is not None,
                self.waveform_followup is not None,
                self.spectrum_freerun is not None,
            )
        )

    @property
    def is_dsox_complete(self) -> bool:
        return all(
            (
                self.delay is not None,
                self.cycle_count is not None,
                self.waveform_delay is not None,
                self.waveform_cycle is not None,
            )
        )

    @property
    def capture_complete(self) -> bool:
        recipe = str(self.metadata.get("recipe", "")).lower()
        if recipe == "ext_imm_pair":
            return self.is_paired_complete
        if recipe == "imm_spectrum_only":
            return self.spectrum_imm is not None
        if recipe == "dsox_only":
            return self.is_dsox_complete
        return self.is_complete
