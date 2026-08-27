"""Runtime factories shared by CLI and desktop UI.

Platform imports stay inside factory functions. This keeps the commercial
package importable in lightweight development environments while still making
all driver imports visible to PyInstaller.
"""

from dataclasses import dataclass

from instrument_capture_studio.adapters.dsox3034a import (
    DSOX3034AAdapter,
    DSOX3034AConfig,
)
from instrument_capture_studio.adapters.fsw import FSWAdapter, FSWConfig


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
    delay_source1: str = "CHANnel1"
    delay_source2: str = "CHANnel2"
    delay_edge1: str = "+1"
    delay_edge2: str = "+1"
    cycle_count_source: str = "CHANnel1"
    waveform_channel: int = 1
    # Two real oscilloscope acquisitions are required for every training
    # sample. Keep the historically qualified defaults but expose them to the
    # GUI so they can be changed and persisted.
    delay_timebase_scale_s: float = 5.0e-7
    cycle_timebase_scale_s: float = 1.0e-4

    def __post_init__(self) -> None:
        if not self.resource.strip():
            raise ValueError("DSO-X resource must not be empty")
        if self.transport_timeout_ms <= 0:
            raise ValueError("DSO-X transport timeout must be greater than 0")
        if self.waveform_channel not in {1, 2, 3, 4}:
            raise ValueError("waveform_channel must be between 1 and 4")
        if self.delay_timebase_scale_s <= 0:
            raise ValueError("delay_timebase_scale_s must be greater than 0")
        if self.cycle_timebase_scale_s <= 0:
            raise ValueError("cycle_timebase_scale_s must be greater than 0")


def build_fsw_adapter(settings: FSWRuntimeSettings) -> FSWAdapter:
    from instrument_core.transport import TransportConfig, VisaTransport
    from instrument_drivers.rohde_schwarz.fsw import RohdeSchwarzFSWDriver

    transport = VisaTransport(
        TransportConfig(
            resource=settings.resource,
            timeout_ms=settings.transport_timeout_ms,
        ),
        backend=settings.backend,
    )

    return FSWAdapter(
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


def build_dsox_adapter(settings: DSOXRuntimeSettings) -> DSOX3034AAdapter:
    from instrument_core.transport import TransportConfig, VisaTransport
    from instrument_drivers.keysight.dsox3000 import KeysightDSOX3000Driver

    transport = VisaTransport(
        TransportConfig(
            resource=settings.resource,
            timeout_ms=settings.transport_timeout_ms,
        ),
        backend=settings.backend,
    )

    return DSOX3034AAdapter(
        address=settings.resource,
        driver=KeysightDSOX3000Driver(transport),
        config=DSOX3034AConfig(
            delay_source1=settings.delay_source1,
            delay_source2=settings.delay_source2,
            delay_edge1=settings.delay_edge1,
            delay_edge2=settings.delay_edge2,
            cycle_count_source=settings.cycle_count_source,
            waveform_channel=settings.waveform_channel,
            delay_timebase_scale_s=settings.delay_timebase_scale_s,
            cycle_timebase_scale_s=settings.cycle_timebase_scale_s,
        ),
    )
