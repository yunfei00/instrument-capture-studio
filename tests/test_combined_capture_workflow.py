from instrument_capture_studio.core.models import (
    JobState,
    StepState,
)
from instrument_capture_studio.core.results import (
    MeasurementResult,
    SpectrumResult,
    WaveformResult,
)
from instrument_capture_studio.workflows.combined import (
    CombinedCaptureWorkflow,
)


class FakeSpectrumAnalyzer:
    def __init__(self, calls):
        self.calls = calls

    def acquire_spectrum(self):
        self.calls.append(
            "fsw_spectrum"
        )

        return SpectrumResult(
            frequencies_hz=[
                500e6,
                600e6,
                700e6,
            ],
            amplitudes_dbm=[
                -80.0,
                -50.0,
                -70.0,
            ],
        )


class FakeOscilloscope:
    def __init__(self, calls):
        self.calls = calls

    def acquire_delay(self):
        self.calls.append(
            "dsox_delay"
        )

        return MeasurementResult(
            measurement="DELAY",
            value=2e-9,
            unit="s",
        )

    def acquire_cycle_count(self):
        self.calls.append(
            "dsox_cycle_count"
        )

        return MeasurementResult(
            measurement="CYCLE_COUNT",
            value=12.0,
            unit="count",
        )

    def acquire_waveform(self):
        self.calls.append(
            "dsox_waveform"
        )

        return WaveformResult(
            channel="CHANnel1",
            time_s=[
                0.0,
                1e-9,
            ],
            voltage_v=[
                0.1,
                0.2,
            ],
        )


def make_workflow(
    *,
    cancel_check=None,
):
    calls = []

    workflow = CombinedCaptureWorkflow(
        spectrum_analyzer=(
            FakeSpectrumAnalyzer(
                calls
            )
        ),
        oscilloscope=(
            FakeOscilloscope(
                calls
            )
        ),
        cancel_check=cancel_check,
    )

    return workflow, calls


def test_combined_capture_runs_in_required_order():
    workflow, calls = make_workflow()

    result = workflow.run(
        "job-001"
    )

    assert result.state == JobState.SUCCEEDED

    assert calls == [
        "fsw_spectrum",
        "dsox_delay",
        "dsox_cycle_count",
        "dsox_waveform",
    ]

    assert all(
        step.state
        == StepState.SUCCEEDED
        for step in result.steps
    )

    assert workflow.context.is_complete is True

    assert (
        result.metadata["capture_complete"]
        is True
    )


def test_combined_capture_collects_results():
    workflow, _ = make_workflow()

    workflow.run(
        "job-results"
    )

    context = workflow.context

    assert context.spectrum is not None
    assert context.spectrum.points == 3

    assert context.delay is not None
    assert context.delay.measurement == "DELAY"
    assert context.delay.value == 2e-9

    assert context.cycle_count is not None
    assert (
        context.cycle_count.measurement
        == "CYCLE_COUNT"
    )
    assert context.cycle_count.value == 12.0

    assert context.waveform is not None
    assert context.waveform.points == 2


def test_combined_capture_resets_context_for_each_job():
    workflow, _ = make_workflow()

    first = workflow.run(
        "job-first"
    )

    first_context = workflow.context

    assert first.state == JobState.SUCCEEDED
    assert first_context.is_complete is True

    second = workflow.run(
        "job-second"
    )

    second_context = workflow.context

    assert second.state == JobState.SUCCEEDED
    assert second_context.is_complete is True

    assert (
        second_context
        is not first_context
    )


def test_combined_capture_can_be_canceled_before_first_step():
    workflow, calls = make_workflow(
        cancel_check=lambda: True,
    )

    result = workflow.run(
        "job-cancel"
    )

    assert result.state == JobState.CANCELED

    assert calls == []

    assert (
        result.steps[0].state
        == StepState.CANCELED
    )

    assert all(
        step.state == StepState.SKIPPED
        for step in result.steps[1:]
    )

    assert (
        workflow.context.is_complete
        is False
    )

    assert (
        result.metadata["capture_complete"]
        is False
    )


def test_failure_keeps_completed_results_and_skips_remaining_steps():
    from instrument_capture_studio.core.exceptions import (
        InstrumentCommunicationError,
    )

    calls = []

    spectrum = FakeSpectrumAnalyzer(
        calls
    )

    class FailingOscilloscope(
        FakeOscilloscope
    ):
        def acquire_delay(self):
            self.calls.append(
                "dsox_delay"
            )

            raise InstrumentCommunicationError(
                "DSO-X connection lost"
            )

    workflow = CombinedCaptureWorkflow(
        spectrum_analyzer=spectrum,
        oscilloscope=FailingOscilloscope(
            calls
        ),
    )

    result = workflow.run(
        "job-partial-failure"
    )

    assert result.state == JobState.FAILED

    assert calls == [
        "fsw_spectrum",
        "dsox_delay",
    ]

    assert (
        result.steps[0].state
        == StepState.SUCCEEDED
    )

    assert (
        result.steps[1].state
        == StepState.FAILED
    )

    assert (
        result.steps[2].state
        == StepState.SKIPPED
    )

    assert (
        result.steps[3].state
        == StepState.SKIPPED
    )

    # 已成功的 FSW 数据必须保留。
    assert workflow.context.spectrum is not None

    # 失败及其后续数据不能伪造。
    assert workflow.context.delay is None
    assert workflow.context.cycle_count is None
    assert workflow.context.waveform is None

    assert (
        result.metadata["capture_complete"]
        is False
    )
