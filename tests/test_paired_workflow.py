from instrument_capture_studio.core.models import JobState, StepState
from instrument_capture_studio.core.results import SpectrumResult, WaveformResult
from instrument_capture_studio.workflows.paired import PairedCaptureWorkflow


class FakeFSW:
    def __init__(self, calls):
        self.calls = calls

    def read_sweep_time_s(self):
        self.calls.append(("fsw", "sweep_time"))
        return 2e-5

    def arm_external_current_setup(self):
        self.calls.append(("fsw", "arm", "EXT"))

    def read_armed_spectrum(
        self,
        *,
        timeout_s=None,
        cancel_check=None,
        trigger_source="EXT",
    ):
        self.calls.append(("fsw", "read", trigger_source))
        return SpectrumResult([700e6], [-50.0], {"trigger_source": "EXT"})

    def acquire_freerun_current_setup(
        self,
        *,
        timeout_s=None,
        cancel_check=None,
    ):
        self.calls.append(("fsw", "freerun", "IMM"))
        return SpectrumResult([700e6], [-55.0], {"trigger_source": "IMM"})


class FakeDSOX:
    def __init__(self, calls):
        self.calls = calls

    def configure_sync_window(self, sweep_time_s):
        self.calls.append(("dsox", "sync_config", sweep_time_s))
        return {
            "requested_position_s": sweep_time_s / 2,
            "requested_scale_s_per_div": sweep_time_s / 10,
            "position_readback_s": sweep_time_s / 2,
            "scale_readback_s_per_div": sweep_time_s / 10,
        }

    def acquire_sync_waveform(self):
        self.calls.append(("dsox", "sync_capture"))
        return WaveformResult(
            channel="CH1",
            time_s=[0.0],
            voltage_v=[0.1],
            sample_rate_hz=1e9,
            metadata={"sample_kind": "sync"},
        )

    def configure_followup_window(self):
        self.calls.append(("dsox", "followup_config"))
        return {
            "requested_position_s": 0.484,
            "requested_scale_s_per_div": 20e-9,
            "position_readback_s": 0.484,
            "scale_readback_s_per_div": 20e-9,
        }

    def acquire_followup_waveform(self):
        self.calls.append(("dsox", "followup_capture"))
        return WaveformResult(
            channel="CH1",
            time_s=[0.0],
            voltage_v=[0.2],
            sample_rate_hz=1e9,
            metadata={"sample_kind": "followup"},
        )


class FakeSink:
    def __init__(self):
        self.context = None

    def save(self, job_id, context):
        self.context = context
        return (
            "metadata.json",
            "spectrum_ext.npz",
            "waveform_sync.npz",
            "waveform_followup.npz",
            "spectrum_freerun.npz",
        )


def test_paired_workflow_runs_hardware_qualified_final_order():
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
        ("fsw", "sweep_time"),
        ("dsox", "sync_config", 2e-5),
        ("fsw", "arm", "EXT"),
        ("dsox", "sync_capture"),
        ("fsw", "read", "EXT"),
        ("dsox", "followup_config"),
        ("dsox", "followup_capture"),
        ("fsw", "freerun", "IMM"),
    ]
    assert result.metadata["schema_version"] == 1
    assert result.metadata["capture_complete"] is True
    assert sink.context.is_paired_complete is True
    assert sink.context.waveform_sync.metadata["sample_kind"] == "sync"
    assert sink.context.waveform_followup.metadata["sample_kind"] == "followup"
    assert sink.context.metadata["waveform_channel"] == "CH1"
    assert sink.context.metadata["fsw_sweep_time_s"] == 2e-5
    assert sink.context.metadata["timing_windows"]["sync"]["requested_position_s"] == 1e-5

    assert [step.name for step in result.steps] == [
        "fsw_sweep_time",
        "dsox_sync_config",
        "fsw_ext_arm",
        "dsox_sync_capture",
        "fsw_ext_read",
        "dsox_followup_config",
        "dsox_followup_capture",
        "fsw_freerun",
        "save_result",
    ]
    assert all(step.state is StepState.SUCCEEDED for step in result.steps)
    assert all(step.started_at is not None for step in result.steps)
    assert all(step.finished_at is not None for step in result.steps)
