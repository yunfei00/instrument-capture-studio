from instrument_capture_studio.core.results import (
    MeasurementResult,
    SpectrumResult,
    WaveformResult,
)
from instrument_capture_studio.workflows.paired_sample import (
    acquire_ext_imm_paired_sample,
)


class FakeFSW:
    def __init__(self, calls):
        self.calls = calls

    def arm_spectrum(self, trigger_source="EXT"):
        self.calls.append(("fsw", "arm", trigger_source))

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
            metadata={"trigger_source": trigger_source},
        )

    def acquire_spectrum_with_trigger(
        self,
        trigger_source,
        *,
        timeout_s=None,
        cancel_check=None,
    ):
        self.calls.append(("fsw", "acquire", trigger_source, timeout_s))
        return SpectrumResult(
            frequencies_hz=[700e6],
            amplitudes_dbm=[-55.0],
            metadata={"trigger_source": trigger_source},
        )


class FakeDSOX:
    def __init__(self, calls):
        self.calls = calls

    def acquire_delay(self):
        self.calls.append(("dsox", "delay"))
        return MeasurementResult("DELAY", 1e-6, "s")

    def acquire_cycle_count(self):
        self.calls.append(("dsox", "cycle"))
        return MeasurementResult("CYCLE_COUNT", 2.0, "count")

    def acquire_waveform(self):
        self.calls.append(("dsox", "waveform"))
        return WaveformResult(
            channel="CH1",
            time_s=[0.0, 1e-9],
            voltage_v=[0.0, 1.0],
            sample_rate_hz=1e9,
        )


def test_ext_is_armed_before_dsox_and_imm_is_last():
    calls = []
    sample = acquire_ext_imm_paired_sample(
        FakeFSW(calls),
        FakeDSOX(calls),
        fsw_timeout_s=5.0,
    )

    assert calls == [
        ("fsw", "arm", "EXT"),
        ("dsox", "delay"),
        ("dsox", "cycle"),
        ("dsox", "waveform"),
        ("fsw", "read_ext", "EXT", 5.0),
        ("fsw", "acquire", "IMM", 5.0),
    ]
    assert sample.spectrum_ext.metadata["trigger_source"] == "EXT"
    assert sample.spectrum_imm.metadata["trigger_source"] == "IMM"
    assert sample.waveform.channel == "CH1"
