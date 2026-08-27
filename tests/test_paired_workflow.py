from instrument_capture_studio.core.models import JobState, StepState
from instrument_capture_studio.core.results import (
    MeasurementResult,
    SpectrumResult,
    WaveformResult,
)
from instrument_capture_studio.workflows.paired import PairedCaptureWorkflow


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
        self.calls.append(("fsw", "read", trigger_source))
        return SpectrumResult([700e6], [-50.0], {"trigger_source": "EXT"})

    def acquire_spectrum_with_trigger(
        self,
        trigger_source,
        *,
        timeout_s=None,
        cancel_check=None,
    ):
        self.calls.append(("fsw", "acquire", trigger_source))
        return SpectrumResult([700e6], [-55.0], {"trigger_source": "IMM"})


class FakeDSOX:
    def __init__(self, calls):
        self.calls = calls

    def acquire_delay_group(self):
        self.calls.append(("dsox", "delay_group"))
        return (
            MeasurementResult(
                "DELAY",
                1e-6,
                "s",
                {"timebase_scale_s": 5e-7},
            ),
            WaveformResult(
                channel="CH1",
                time_s=[0.0],
                voltage_v=[0.1],
                sample_rate_hz=1e9,
                metadata={
                    "sample_kind": "delay",
                    "timebase_scale_s": 5e-7,
                },
            ),
        )

    def acquire_cycle_group(self):
        self.calls.append(("dsox", "cycle_group"))
        return (
            MeasurementResult(
                "CYCLE_COUNT",
                2.0,
                "count",
                {"timebase_scale_s": 1e-4},
            ),
            WaveformResult(
                channel="CH1",
                time_s=[0.0],
                voltage_v=[0.2],
                sample_rate_hz=1e6,
                metadata={
                    "sample_kind": "cycle_count",
                    "timebase_scale_s": 1e-4,
                },
            ),
        )


class FakeSink:
    def __init__(self):
        self.context = None

    def save(self, job_id, context):
        self.context = context
        return (
            "metadata.json",
            "spectrum_ext.npz",
            "spectrum_imm.npz",
            "waveform_delay.npz",
            "waveform_cycle.npz",
        )


def test_paired_workflow_runs_real_order_and_records_two_dsox_groups():
    calls = []
    sink = FakeSink()
    workflow = PairedCaptureWorkflow(
        FakeFSW(calls),
        FakeDSOX(calls),
        fsw_timeout_s=5.0,
        result_sink=sink,
    )

    result = workflow.run("job-paired")

    assert result.state is JobState.SUCCEEDED
    assert calls == [
        ("fsw", "arm", "EXT"),
        ("dsox", "delay_group"),
        ("fsw", "read", "EXT"),
        ("dsox", "cycle_group"),
        ("fsw", "acquire", "IMM"),
    ]
    assert result.metadata["schema_version"] == 1
    assert result.metadata["capture_complete"] is True
    assert sink.context.is_paired_complete is True
    assert sink.context.waveform_delay.metadata["sample_kind"] == "delay"
    assert sink.context.waveform_cycle.metadata["sample_kind"] == "cycle_count"
    assert sink.context.metadata["waveform_channel"] == "CH1"

    assert [step.name for step in result.steps] == [
        "fsw_ext_arm",
        "dsox_delay_group",
        "fsw_ext_read",
        "dsox_cycle_group",
        "fsw_imm",
        "save_result",
    ]
    assert all(step.state is StepState.SUCCEEDED for step in result.steps)
    assert all(step.started_at is not None for step in result.steps)
    assert all(step.finished_at is not None for step in result.steps)
