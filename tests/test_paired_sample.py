from instrument_capture_studio.core.results import SpectrumResult, WaveformResult
from instrument_capture_studio.workflows.paired_sample import (
    acquire_ext_imm_paired_sample,
)


class FakeFSW:
    def __init__(self, calls):
        self.calls = calls

    def read_sweep_time_s(self):
        self.calls.append(("fsw", "sweep_time"))
        return 2e-5

    def arm_external_current_setup(self):
        self.calls.append(("fsw", "arm_single", "EXT"))

    def read_armed_spectrum(
        self,
        *,
        timeout_s=None,
        cancel_check=None,
        trigger_source="EXT",
    ):
        self.calls.append(("fsw", "read_ext", trigger_source, timeout_s))
        return SpectrumResult(
            frequencies_hz=[700e6],
            amplitudes_dbm=[-50.0],
            metadata={
                "trigger_source": trigger_source,
                "acquisition_mode": "single",
            },
        )

    def acquire_freerun_current_setup(
        self,
        *,
        timeout_s=None,
        cancel_check=None,
    ):
        self.calls.append(("fsw", "single", "IMM", timeout_s))
        return SpectrumResult(
            frequencies_hz=[700e6],
            amplitudes_dbm=[-55.0],
            metadata={
                "trigger_source": "IMM",
                "acquisition_mode": "single",
            },
        )


class FakeDSOX:
    def __init__(self, calls):
        self.calls = calls

    def configure_sync_window(self, sweep_time_s):
        self.calls.append(("dsox", "sync_config", sweep_time_s))
        return {"position_readback_s": sweep_time_s / 2}

    def acquire_sync_waveform(self, *, cancel_check=None):
        self.calls.append(("dsox", "single_sync"))
        return WaveformResult(
            channel="CH1",
            time_s=[0.0, 1e-9],
            voltage_v=[0.0, 1.0],
            sample_rate_hz=1e9,
            metadata={
                "sample_kind": "sync",
                "acquisition_mode": "single",
                "acquisition_command": ":SINGle",
            },
        )

    def configure_followup_window(self):
        self.calls.append(("dsox", "followup_config"))
        return {"position_readback_s": 0.484}

    def acquire_followup_waveform(self, *, cancel_check=None):
        self.calls.append(("dsox", "single_followup"))
        return WaveformResult(
            channel="CH1",
            time_s=[0.0, 1e-6],
            voltage_v=[0.0, 0.5],
            sample_rate_hz=1e6,
            metadata={
                "sample_kind": "followup",
                "acquisition_mode": "single",
                "acquisition_command": ":SINGle",
            },
        )


def test_final_paired_sample_follows_verified_single_hardware_order():
    calls = []
    sample = acquire_ext_imm_paired_sample(
        FakeFSW(calls),
        FakeDSOX(calls),
        fsw_timeout_s=5.0,
    )

    assert calls == [
        ("fsw", "sweep_time"),
        ("dsox", "sync_config", 2e-5),
        ("fsw", "arm_single", "EXT"),
        ("dsox", "single_sync"),
        ("fsw", "read_ext", "EXT", 5.0),
        ("dsox", "followup_config"),
        ("dsox", "single_followup"),
        ("fsw", "single", "IMM", 5.0),
    ]
    assert sample.sweep_time_s == 2e-5
    assert sample.spectrum_ext.metadata["acquisition_mode"] == "single"
    assert sample.spectrum_freerun.metadata["acquisition_mode"] == "single"
    assert sample.waveform_sync.metadata["acquisition_command"] == ":SINGle"
    assert sample.waveform_followup.metadata["acquisition_command"] == ":SINGle"
