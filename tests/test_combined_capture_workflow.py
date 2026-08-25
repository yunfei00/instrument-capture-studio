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
        self.last_timeout_s = None

    def acquire_spectrum(
        self,
        *,
        timeout_s: float | None = None,
        cancel_check=None,
    ):
        self.last_timeout_s = timeout_s
        self.last_cancel_check = cancel_check

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
    fsw_timeout_s=None,
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
        fsw_timeout_s=fsw_timeout_s,
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



def test_combined_capture_passes_fsw_remaining_timeout():
    calls = []

    spectrum = FakeSpectrumAnalyzer(
        calls
    )

    workflow = CombinedCaptureWorkflow(
        spectrum_analyzer=spectrum,
        oscilloscope=FakeOscilloscope(
            calls
        ),
        fsw_timeout_s=7.5,
    )

    result = workflow.run(
        "job-fsw-timeout"
    )

    assert result.state == JobState.SUCCEEDED

    assert spectrum.last_timeout_s is not None

    assert (
        0.0
        < spectrum.last_timeout_s
        <= 7.5
    )

    assert (
        result.steps[0]
        .metadata["timeout_s"]
        == 7.5
    )


def test_fsw_trigger_timeout_fails_workflow_and_skips_remaining_steps():
    from instrument_capture_studio.adapters.fsw import (
        FSWAdapter,
    )
    from instrument_capture_studio.core.exceptions import (
        InstrumentTimeoutError,
    )

    PlatformTriggerTimeoutError = type(
        "TriggerTimeoutError",
        (Exception,),
        {},
    )

    class TimeoutFSWDriver:
        def acquire_trace_ascii(
            self,
            *,
            channel=1,
            window=1,
            trace=1,
            timeout_s=None,
            cancel_check=None,
        ):
            assert timeout_s is not None
            assert 0.0 < timeout_s <= 0.5

            raise PlatformTriggerTimeoutError(
                "measurement trigger timeout"
            )

    calls = []

    spectrum = FSWAdapter(
        address="MOCK::FSW",
        driver=TimeoutFSWDriver(),
    )

    workflow = CombinedCaptureWorkflow(
        spectrum_analyzer=spectrum,
        oscilloscope=FakeOscilloscope(
            calls
        ),
        fsw_timeout_s=0.5,
    )

    result = workflow.run(
        "job-fsw-trigger-timeout"
    )

    assert result.state == JobState.FAILED

    assert (
        result.steps[0].state
        == StepState.FAILED
    )

    assert (
        result.steps[0]
        .metadata["error_type"]
        == InstrumentTimeoutError.__name__
    )

    assert (
        result.steps[0]
        .metadata["timeout_s"]
        == 0.5
    )

    assert (
        "measurement trigger timeout"
        in result.steps[0].error
    )

    assert all(
        step.state == StepState.SKIPPED
        for step in result.steps[1:]
    )

    # FSW 已失败，示波器绝不能继续执行。
    assert calls == []

    assert workflow.context.spectrum is None
    assert workflow.context.delay is None
    assert workflow.context.cycle_count is None
    assert workflow.context.waveform is None

    assert (
        result.metadata["capture_complete"]
        is False
    )


def test_fsw_runtime_cancel_marks_job_canceled():
    from instrument_capture_studio.adapters.fsw import (
        FSWAdapter,
    )

    PlatformOperationCanceledError = type(
        "OperationCanceledError",
        (Exception,),
        {},
    )

    class CancelableFSWDriver:
        def acquire_trace_ascii(
            self,
            *,
            channel=1,
            window=1,
            trace=1,
            timeout_s=None,
            cancel_check=None,
        ):
            assert cancel_check is not None

            if cancel_check():
                raise PlatformOperationCanceledError(
                    "measurement canceled"
                )

            raise AssertionError(
                "cancel was not observed"
            )

    state = {
        "checks": 0,
    }

    def cancel_check():
        state["checks"] += 1

        # 第一次：Runner 开始 Step 前检查 → False
        # 第二次：FSW 正在运行时检查 → True
        return (
            state["checks"]
            >= 2
        )

    calls = []

    workflow = CombinedCaptureWorkflow(
        spectrum_analyzer=FSWAdapter(
            address="MOCK::FSW",
            driver=CancelableFSWDriver(),
        ),
        oscilloscope=FakeOscilloscope(
            calls
        ),
        cancel_check=cancel_check,
    )

    result = workflow.run(
        "job-fsw-runtime-cancel"
    )

    assert result.state == JobState.CANCELED

    assert (
        result.steps[0].state
        == StepState.CANCELED
    )

    assert all(
        step.state == StepState.SKIPPED
        for step in result.steps[1:]
    )

    assert calls == []

    assert workflow.context.spectrum is None

    assert (
        result.metadata["capture_complete"]
        is False
    )


def test_combined_capture_executes_save_result_step():
    class RecordingResultSink:
        def __init__(self):
            self.job_id = None
            self.context = None

        def save(
            self,
            job_id,
            context,
        ):
            self.job_id = job_id
            self.context = context

            return (
                "memory://job-save-result",
            )

    calls = []

    sink = RecordingResultSink()

    workflow = CombinedCaptureWorkflow(
        spectrum_analyzer=FakeSpectrumAnalyzer(
            calls
        ),
        oscilloscope=FakeOscilloscope(
            calls
        ),
        result_sink=sink,
    )

    result = workflow.run(
        "job-save-result"
    )

    assert result.state == JobState.SUCCEEDED

    assert [
        step.name
        for step in result.steps
    ] == [
        "fsw_spectrum",
        "dsox_delay",
        "dsox_cycle_count",
        "dsox_waveform",
        "save_result",
    ]

    assert (
        result.steps[-1].state
        == StepState.SUCCEEDED
    )

    assert sink.job_id == "job-save-result"

    assert sink.context is workflow.context

    assert sink.context.is_complete is True

    assert (
        result.metadata["result_saved"]
        is True
    )

    assert result.output_files == [
        "memory://job-save-result"
    ]


def test_combined_capture_preserves_initial_metadata():
    calls = []

    workflow = CombinedCaptureWorkflow(
        spectrum_analyzer=FakeSpectrumAnalyzer(
            calls
        ),
        oscilloscope=FakeOscilloscope(
            calls
        ),
        initial_metadata={
            "instruments": {
                "test": {
                    "model": "TEST",
                }
            }
        },
    )

    result = workflow.run(
        "job-initial-metadata"
    )

    assert (
        workflow.context.metadata[
            "instruments"
        ][
            "test"
        ][
            "model"
        ]
        == "TEST"
    )

    assert (
        result.metadata[
            "instruments"
        ][
            "test"
        ][
            "model"
        ]
        == "TEST"
    )
