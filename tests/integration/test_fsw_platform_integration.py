import sys
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parents[2]

PLATFORM_ROOT = (
    APP_ROOT.parent
    / "instrument-automation-platform"
)

if not PLATFORM_ROOT.exists():
    pytest.skip(
        "instrument-automation-platform sibling repo not found",
        allow_module_level=True,
    )

for package in (
    "instrument_core",
    "instrument_scpi",
    "instrument_drivers",
):
    sys.path.insert(
        0,
        str(
            PLATFORM_ROOT
            / "packages"
            / package
            / "src"
        ),
    )


from instrument_core.transport import MockTransport
from instrument_drivers.rohde_schwarz.fsw import (
    RohdeSchwarzFSWDriver,
)

from instrument_capture_studio.adapters.fsw import (
    FSWAdapter,
    FSWConfig,
)
from instrument_capture_studio.core.models import (
    InstrumentState,
)


def test_fsw_adapter_with_real_platform_driver():
    transport = MockTransport()

    driver = RohdeSchwarzFSWDriver(
        transport
    )

    adapter = FSWAdapter(
        address="MOCK::FSW",
        driver=driver,
        config=FSWConfig(
            center_frequency_hz=150e6,
            span_hz=100e6,
            rbw_hz=1e6,
            vbw_hz=3e6,
            trigger_source="EXT",
            channel=1,
            window=1,
            trace=1,
        ),
    )

    # connect() -> *IDN?
    transport.queue_response(
        "Rohde&Schwarz,"
        "FSW,"
        "123456,"
        "6.30\n"
    )

    adapter.connect()

    status = adapter.get_status()

    assert adapter.is_connected() is True
    assert status.state == InstrumentState.CONNECTED
    assert status.model == "FSW"
    assert status.serial_number == "123456"
    assert status.firmware_version == "6.30"

    # acquire_trace_ascii() responses:
    # *OPC?
    transport.queue_response(
        "1\n"
    )

    # start frequency
    transport.queue_response(
        "100000000\n"
    )

    # stop frequency
    transport.queue_response(
        "200000000\n"
    )

    # TRACE1
    transport.queue_response(
        "-80,-60,-70\n"
    )

    result = adapter.acquire_spectrum()

    assert result.frequencies_hz == [
        100e6,
        150e6,
        200e6,
    ]

    assert result.amplitudes_dbm == [
        -80.0,
        -60.0,
        -70.0,
    ]

    assert result.points == 3

    assert result.metadata["start_hz"] == 100e6
    assert result.metadata["stop_hz"] == 200e6
    assert result.metadata["transfer_format"] == "ASCII"

    required_writes = [
        "SENSe:FREQuency:CENTer 150000000.0",
        "SENSe:FREQuency:SPAN 100000000.0",
        "SENSe:BANDwidth:RESolution 1000000.0",
        "SENSe:BANDwidth:VIDeo 3000000.0",
        "TRIGger:SEQuence:SOURce EXT",
        "INITiate1:CONTinuous OFF",
        "FORMat:DATA ASCii",
        "INITiate1:IMMediate",
        "*OPC?",
        "SENSe:FREQuency:STARt?",
        "SENSe:FREQuency:STOP?",
        "TRACe1:DATA? TRACE1",
    ]

    for command in required_writes:
        assert command in transport.writes

    adapter.disconnect()

    assert adapter.is_connected() is False
