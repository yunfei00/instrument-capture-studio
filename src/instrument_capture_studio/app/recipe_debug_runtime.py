"""Runtime factories for the stateful engineering recipe debugger."""

from __future__ import annotations

from instrument_capture_studio.app.runtime import DSOXRuntimeSettings, FSWRuntimeSettings


def build_debug_fsw_driver(settings: FSWRuntimeSettings):
    from instrument_core.transport import TransportConfig, VisaTransport
    from instrument_drivers.rohde_schwarz.fsw import RohdeSchwarzFSWDriver

    transport = VisaTransport(
        TransportConfig(
            resource=settings.resource,
            timeout_ms=settings.transport_timeout_ms,
        ),
        backend=settings.backend,
    )
    return RohdeSchwarzFSWDriver(transport)


def build_debug_dsox_driver(settings: DSOXRuntimeSettings):
    from instrument_core.transport import TransportConfig, VisaTransport
    from instrument_drivers.keysight.dsox3000 import KeysightDSOX3000Driver

    transport = VisaTransport(
        TransportConfig(
            resource=settings.resource,
            timeout_ms=settings.transport_timeout_ms,
        ),
        backend=settings.backend,
    )
    return KeysightDSOX3000Driver(transport)
