from instrument_capture_studio.adapters.fsw_capture_settings import (
    read_fsw_frontend_snapshot,
    read_fsw_measurement_snapshot,
)
from instrument_capture_studio.data.metadata import build_capture_metadata
from instrument_capture_studio.workflows.context import CaptureContext


class FakeDriver:
    def __init__(self):
        self.commands: list[str] = []

    def query(self, command: str) -> str:
        self.commands.append(command)
        values = {
            "INPut:GAIN:STATe?": "1",
            "INPut:GAIN:VALue?": "30",
            "INPut:ATTenuation:AUTO?": "0",
            "INPut:ATTenuation?": "12",
            "SENSe:BANDwidth:RESolution?": "1.0000000E+07",
            "SENSe:BANDwidth:VIDeo?": "3.0000000E+06",
        }
        return values[command]


class FakeFSWAdapter:
    name = "FSW"

    def __init__(self):
        self._driver = FakeDriver()


def test_fsw_frontend_snapshot_is_read_once_per_adapter_session():
    adapter = FakeFSWAdapter()

    first = read_fsw_frontend_snapshot(adapter)
    second = read_fsw_frontend_snapshot(adapter)

    assert first["preamp_enabled"] is True
    assert first["preamp_db"] == 30
    assert first["rf_attenuation_auto"] is False
    assert first["rf_attenuation_db"] == 12.0
    assert first["read_only"] is True
    assert second == first
    assert adapter._driver.commands == [
        "INPut:GAIN:STATe?",
        "INPut:GAIN:VALue?",
        "INPut:ATTenuation:AUTO?",
        "INPut:ATTenuation?",
    ]


def test_fsw_bandwidth_snapshot_records_instrument_readback_not_gui_default():
    adapter = FakeFSWAdapter()

    first = read_fsw_measurement_snapshot(adapter)
    second = read_fsw_measurement_snapshot(adapter)

    assert first["source"] == "instrument_readback"
    assert first["rbw_hz"] == 10e6
    assert first["vbw_hz"] == 3e6
    assert first["read_only"] is True
    assert second == first
    assert adapter._driver.commands == [
        "SENSe:BANDwidth:RESolution?",
        "SENSe:BANDwidth:VIDeo?",
    ]


def test_paired_metadata_exposes_frontend_bandwidth_sweep_and_scope_windows():
    frontend = {
        "preamp_enabled": True,
        "preamp_db": 15,
        "rf_attenuation_auto": False,
        "rf_attenuation_db": 10.0,
    }
    measurement = {
        "source": "instrument_readback",
        "rbw_hz": 10e6,
        "vbw_hz": 3e6,
    }
    context = CaptureContext(
        metadata={
            "recipe": "ext_imm_pair",
            "fsw_sweep_time_s": 0.01,
            "instruments": {
                "spectrum_analyzer": {
                    "name": "FSW",
                    "frontend": frontend,
                    "measurement": measurement,
                }
            },
            "timing_windows": {
                "sync": {
                    "requested_position_s": 0.005,
                    "requested_scale_s_per_div": 0.001,
                    "position_readback_s": 0.005,
                    "scale_readback_s_per_div": 0.001,
                },
                "followup": {
                    "requested_position_s": 0.484,
                    "requested_scale_s_per_div": 20e-9,
                    "position_readback_s": 0.484,
                    "scale_readback_s_per_div": 20e-9,
                },
            },
        }
    )

    metadata = build_capture_metadata("job-1", context)
    parameters = metadata["acquisition_parameters"]

    assert parameters["fsw"]["sweep_time_s"] == 0.01
    assert parameters["fsw"]["rbw_hz"] == 10e6
    assert parameters["fsw"]["vbw_hz"] == 3e6
    assert parameters["fsw"]["measurement"] == measurement
    assert parameters["fsw"]["frontend"] == frontend
    assert parameters["dsox"]["sync"]["requested_position_s"] == 0.005
    assert parameters["dsox"]["sync"]["requested_scale_s_per_div"] == 0.001
    assert parameters["dsox"]["followup"]["requested_position_s"] == 0.484
    assert parameters["dsox"]["followup"]["requested_scale_s_per_div"] == 20e-9
