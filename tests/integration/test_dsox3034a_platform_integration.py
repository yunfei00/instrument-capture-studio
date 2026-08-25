import struct
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
from instrument_drivers.keysight.dsox3000 import (
    KeysightDSOX3000Driver,
)

from instrument_capture_studio.adapters.dsox3034a import (
    DSOX3034AAdapter,
)
from instrument_capture_studio.core.models import (
    InstrumentState,
)


def test_dsox3034a_adapter_with_real_platform_driver():
    transport = MockTransport()

    driver = KeysightDSOX3000Driver(
        transport
    )

    adapter = DSOX3034AAdapter(
        address="MOCK::DSOX3034A",
        driver=driver,
    )

    # connect() -> *IDN?
    transport.queue_response(
        "KEYSIGHT TECHNOLOGIES,"
        "DSO-X 3034A,"
        "MY123456,"
        "02.50\n"
    )

    adapter.connect()

    status = adapter.get_status()

    assert adapter.is_connected() is True
    assert status.state == InstrumentState.CONNECTED
    assert status.model == "DSO-X 3034A"
    assert status.serial_number == "MY123456"
    assert status.firmware_version == "02.50"

    assert "*IDN?" in transport.writes

    # DELAY
    transport.queue_response(
        "1.250000E-06\n"
    )

    delay = adapter.acquire_delay()

    assert delay.measurement == "DELAY"
    assert delay.value == 1.25e-6
    assert delay.unit == "s"

    assert (
        ":MEASure:DEFine DELay,+1,+1"
        in transport.writes
    )

    assert (
        ":MEASure:DELay? CHANnel1,CHANnel2"
        in transport.writes
    )

    # Cycle count -> Keysight NPUlSes
    transport.queue_response(
        "12\n"
    )

    count = adapter.acquire_cycle_count()

    assert count.measurement == "CYCLE_COUNT"
    assert count.value == 12.0
    assert count.unit == "count"

    assert (
        ":MEASure:NPUlSes? CHANnel1"
        in transport.writes
    )

    # Waveform
    transport.queue_response(
        "1,0,4,1,"
        "1.0E-6,0,0,"
        "1.0E-3,0,0\n"
    )

    transport.queue_response(
        "LSBFirst\n"
    )

    transport.queue_response(
        "0\n"
    )

    payload = struct.pack(
        "<4h",
        0,
        100,
        -100,
        200,
    )

    header = (
        b"#1"
        + str(len(payload)).encode()
    )

    transport.queue_raw_response(
        header
        + payload
        + b"\n"
    )

    waveform = adapter.acquire_waveform()

    assert waveform.channel == "CH1"

    assert waveform.time_s == [
        0.0,
        1e-6,
        2e-6,
        3e-6,
    ]

    assert waveform.voltage_v == [
        0.0,
        0.1,
        -0.1,
        0.2,
    ]

    assert waveform.points == 4
    assert waveform.sample_rate_hz == 1e6

    assert ":DIGitize CHANnel1" in transport.writes
    assert ":WAVeform:DATA?" in transport.writes

    adapter.disconnect()

    assert adapter.is_connected() is False
