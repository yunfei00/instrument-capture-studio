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

    def acquire_waveform(self):
        self.calls.append(("dsox", "waveform"))
        return WaveformResult(
            channel="CH1",
            time_s=[0.0],
            voltage_v=[0.1],
            sample_rate_hz=1e9,
        )

    def acquire_delay(self):
        self.calls.append(("dsox", "delay"))
        return MeasurementResult("DELAY", 1e-6, "s")

    def acquire_cycle_count(self):
        self.calls.append(("dsox", "cycle"))
        return MeasurementResult("CYCLE_COUNT", 2.0, "count")


class FakeSink:
    def __init__(self):
        self.context = None

    def save(self, job_id, context):
        self.context = context
        return ("metadata.json", "spectrum_ext.npz", "spectrum_imm.npz", "waveform.npz")


def test_paired_workflow_runs_real_order_and_records_step_times():
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
        ("dsox", "waveform"),
        ("dsox", "delay"),
        ("dsox", "cycle"),
        ("fsw", "read", "EXT"),
        ("fsw", "acquire", "IMM"),
    ]
    assert result.metadata["schema_version"] == 2
    assert result.metadata["capture_complete"] is True
    assert sink.context.is_paired_complete is True
    assert sink.context.metadata["waveform_channel"] == "CH1"

    assert [step.name for step in result.steps] == [
        "fsw_ext_arm",
        "dsox_waveform",
        "dsox_delay",
        "dsox_cycle_count",
        "fsw_ext_read",
        "fsw_imm",
        "save_result",
    ]
    assert all(step.state is StepState.SUCCEEDED for step in result.steps)
    assert all(step.started_at is not None for step in result.steps)
    assert all(step.finished_at is not None for step in result.steps)
