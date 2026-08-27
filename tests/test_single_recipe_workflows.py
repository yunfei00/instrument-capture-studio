from instrument_capture_studio.core.models import JobState
from instrument_capture_studio.core.results import SpectrumResult, WaveformResult
from instrument_capture_studio.workflows.single_recipes import (
    DSOXOnlyWorkflow,
    ImmSpectrumOnlyWorkflow,
)


class FakeSink:
    def __init__(self):
        self.context = None

    def save(self, job_id, context):
        self.context = context
        return ("metadata.json",)


class FakeFSW:
    def __init__(self):
        self.trigger = None

    def acquire_spectrum_with_trigger(
        self,
        trigger_source,
        *,
        timeout_s=None,
        cancel_check=None,
    ):
        self.trigger = trigger_source
        return SpectrumResult([700e6], [-60.0], {"trigger_source": trigger_source})


class FakeDSOX:
    def acquire_waveform(self):
        return WaveformResult(
            channel="CH1",
            time_s=[0.0],
            voltage_v=[0.2],
            sample_rate_hz=1e9,
        )


def test_imm_spectrum_only_is_complete_without_dsox():
    sink = FakeSink()
    fsw = FakeFSW()
    result = ImmSpectrumOnlyWorkflow(fsw, result_sink=sink).run("job-imm")

    assert result.state is JobState.SUCCEEDED
    assert result.metadata["recipe"] == "imm_spectrum_only"
    assert result.metadata["capture_complete"] is True
    assert fsw.trigger == "IMM"
    assert sink.context.spectrum is not None
    assert sink.context.waveform is None


def test_dsox_only_is_complete_without_fsw_and_uses_selected_waveform():
    sink = FakeSink()
    result = DSOXOnlyWorkflow(FakeDSOX(), result_sink=sink).run("job-dsox")

    assert result.state is JobState.SUCCEEDED
    assert result.metadata["recipe"] == "dsox_only"
    assert result.metadata["capture_complete"] is True
    assert sink.context.waveform.channel == "CH1"
    assert sink.context.spectrum is None
