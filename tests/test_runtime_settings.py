import pytest

from instrument_capture_studio.app.runtime import (
    DSOXRuntimeSettings,
    FSWRuntimeSettings,
)


def test_fsw_runtime_settings_accept_valid_values():
    settings = FSWRuntimeSettings(
        resource="TCPIP0::FSW::inst0::INSTR",
        center_frequency_hz=600e6,
        span_hz=200e6,
    )

    assert settings.transport_timeout_ms == 15000
    assert settings.step_timeout_s == 30.0
    assert settings.center_frequency_hz == 600e6


def test_fsw_runtime_settings_reject_empty_resource():
    with pytest.raises(ValueError, match="resource"):
        FSWRuntimeSettings(resource="   ")


def test_dsox_runtime_settings_accept_valid_values():
    settings = DSOXRuntimeSettings(
        resource="TCPIP0::DSOX::inst0::INSTR",
        waveform_channel=4,
    )

    assert settings.transport_timeout_ms == 10000
    assert settings.single_timeout_s == 30.0
    assert settings.waveform_channel == 4


def test_dsox_runtime_settings_reject_invalid_channel():
    with pytest.raises(ValueError, match="waveform_channel"):
        DSOXRuntimeSettings(
            resource="TCPIP0::DSOX::inst0::INSTR",
            waveform_channel=5,
        )


def test_dsox_runtime_settings_reject_invalid_single_timeout():
    with pytest.raises(ValueError, match="Single timeout"):
        DSOXRuntimeSettings(
            resource="TCPIP0::DSOX::inst0::INSTR",
            single_timeout_s=0.0,
        )
