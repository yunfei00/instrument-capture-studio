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

    def acquire_delay_group(self):
        self.calls.append(("dsox", "delay_group"))
        return (
            MeasurementResult("DELAY", 1e-6, "s"),
            WaveformResult(
                channel="CH1",
                time_s=[0.0, 1e-9],
                voltage_v=[0.0, 1.0],
                sample_rate_hz=1e9,
                metadata={"sample_kind": "delay"},
            ),
        )

    def acquire_cycle_group(self):
        self.calls.append(("dsox", "cycle_group"))
        return (
            MeasurementResult("CYCLE_COUNT", 2.0, "count"),
            WaveformResult(
                channel="CH1",
                time_s=[0.0, 1e-6],
                voltage_v=[0.0, 0.5],
                sample_rate_hz=1e6,
                metadata={"sample_kind": "cycle_count"},
            ),
        )


def test_ext_is_armed_before_first_dsox_group_and_imm_is_last():
    calls = []
    sample = acquire_ext_imm_paired_sample(
        FakeFSW(calls),
        FakeDSOX(calls),
        fsw_timeout_s=5.0,
    )

    assert calls == [
        ("fsw", "arm", "EXT"),
        ("dsox", "delay_group"),
        ("fsw", "read_ext", "EXT", 5.0),
        ("dsox", "cycle_group"),
        ("fsw", "acquire", "IMM", 5.0),
    ]
    assert sample.spectrum_ext.metadata["trigger_source"] == "EXT"
    assert sample.spectrum_imm.metadata["trigger_source"] == "IMM"
    assert sample.waveform_delay.metadata["sample_kind"] == "delay"
    assert sample.waveform_cycle.metadata["sample_kind"] == "cycle_count"
