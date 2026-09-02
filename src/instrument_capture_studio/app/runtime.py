"""Runtime factories shared by CLI and desktop UI.

Platform imports stay inside factory functions. This keeps the commercial
package importable in lightweight development environments while still making
all driver imports visible to PyInstaller.
"""

from dataclasses import dataclass

from instrument_capture_studio.adapters.dsox3034a import DSOX3034AConfig
from instrument_capture_studio.adapters.formal_recipe import (
    FormalDSOXAdapter,
    FormalDSOXConfig,
    FormalFSWAdapter,
)
from instrument_capture_studio.adapters.fsw import FSWConfig


@dataclass(frozen=True)
class FSWRuntimeSettings:
    resource: str
    backend: str | None = None
    transport_timeout_ms: int = 15000
    step_timeout_s: float = 30.0
    center_frequency_hz: float | None = None
    span_hz: float | None = None
    rbw_hz: float | None = None
    vbw_hz: float | None = None
    trigger_source: str | None = None

    def __post_init__(self) -> None:
        if not self.resource.strip():
            raise ValueError("FSW resource must not be empty")
        if self.transport_timeout_ms <= 0:
            raise ValueError("FSW transport timeout must be greater than 0")
        if self.step_timeout_s <= 0:
            raise ValueError("FSW step timeout must be greater than 0")


@dataclass(frozen=True)
class DSOXRuntimeSettings:
    resource: str
    backend: str | None = None
    transport_timeout_ms: int = 10000
    single_timeout_s: float = 30.0
    delay_source1: str = "CHANnel1"
    delay_source2: str = "CHANnel2"
    delay_edge1: str = "+1"
    delay_edge2: str = "+1"
    cycle_count_source: str = "CHANnel1"
    waveform_channel: int = 1
    # Legacy DSO-X-only recipe settings are retained for the standalone tool.
    delay_timebase_scale_s: float = 5.0e-7
    cycle_timebase_scale_s: float = 1.0e-4
    # Final paired recipe: the first window is derived from FSW Sweep Time.
    # Only the second independent scope capture is user-configurable.
    followup_position_s: float = 0.484
    followup_scale_s: float = 20e-9
    # Optional post-waveform Snapshot All evidence. Disabled by default because
    # it performs 31 additional scalar measurement queries per scope waveform.
    snapshot_all_enabled: bool = False

    def __post_init__(self) -> None:
        if not self.resource.strip():
            raise ValueError("DSO-X resource must not be empty")
        if self.transport_timeout_ms <= 0:
            raise ValueError("DSO-X transport timeout must be greater than 0")
        if self.single_timeout_s <= 0:
            raise ValueError("DSO-X Single timeout must be greater than 0")
        if self.waveform_channel not in {1, 2, 3, 4}:
            raise ValueError("waveform_channel must be between 1 and 4")
        if self.delay_timebase_scale_s <= 0:
            raise ValueError("delay_timebase_scale_s must be greater than 0")
        if self.cycle_timebase_scale_s <= 0:
            raise ValueError("cycle_timebase_scale_s must be greater than 0")
        if self.followup_position_s < 0:
            raise ValueError("followup_position_s must not be negative")
        if self.followup_scale_s <= 0:
            raise ValueError("followup_scale_s must be greater than 0")


def build_fsw_adapter(settings: FSWRuntimeSettings) -> FormalFSWAdapter:
    from instrument_core.transport import TransportConfig, VisaTransport
    from instrument_drivers.rohde_schwarz.fsw import RohdeSchwarzFSWDriver

    transport = VisaTransport(
        TransportConfig(
            resource=settings.resource,
            timeout_ms=settings.transport_timeout_ms,
        ),
        backend=settings.backend,
    )

    return FormalFSWAdapter(
        address=settings.resource,
        driver=RohdeSchwarzFSWDriver(transport),
        config=FSWConfig(
            center_frequency_hz=settings.center_frequency_hz,
            span_hz=settings.span_hz,
            rbw_hz=settings.rbw_hz,
            vbw_hz=settings.vbw_hz,
            trigger_source=settings.trigger_source,
        ),
    )


def build_dsox_adapter(settings: DSOXRuntimeSettings) -> FormalDSOXAdapter:
    from instrument_core.transport import TransportConfig, VisaTransport
    from instrument_drivers.keysight.dsox3000 import KeysightDSOX3000Driver

    transport = VisaTransport(
        TransportConfig(
            resource=settings.resource,
            timeout_ms=settings.transport_timeout_ms,
        ),
        backend=settings.backend,
    )

    return FormalDSOXAdapter(
        address=settings.resource,
        driver=KeysightDSOX3000Driver(transport),
        config=FormalDSOXConfig(
            delay_source1=settings.delay_source1,
            delay_source2=settings.delay_source2,
            delay_edge1=settings.delay_edge1,
            delay_edge2=settings.delay_edge2,
            cycle_count_source=settings.cycle_count_source,
            waveform_channel=settings.waveform_channel,
            delay_timebase_scale_s=settings.delay_timebase_scale_s,
            cycle_timebase_scale_s=settings.cycle_timebase_scale_s,
            followup_position_s=settings.followup_position_s,
            followup_scale_s=settings.followup_scale_s,
            single_timeout_s=settings.single_timeout_s,
            snapshot_all_enabled=settings.snapshot_all_enabled,
        ),
    )
