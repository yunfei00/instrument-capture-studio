import time

import pytest

from instrument_capture_studio.core.exceptions import (
    CaptureCanceledError,
    InstrumentCommunicationError,
)
from instrument_capture_studio.core.models import (
    JobState,
    StepState,
)
from instrument_capture_studio.workflows.base import (
    CaptureStepDefinition,
)
from instrument_capture_studio.workflows.runner import (
    SequentialWorkflowRunner,
)


def make_steps():
    return (
        CaptureStepDefinition(
            "fsw_spectrum"
        ),
        CaptureStepDefinition(
            "dsox_delay"
        ),
        CaptureStepDefinition(
            "dsox_cycles"
        ),
        CaptureStepDefinition(
            "save_result"
        ),
    )


def test_workflow_success():
    calls = []

    def executor(name):
        def run(execution):
            calls.append(name)

        return run

    runner = SequentialWorkflowRunner(
        steps=make_steps(),
        executors={
            "fsw_spectrum": executor(
                "fsw_spectrum"
            ),
            "dsox_delay": executor(
                "dsox_delay"
            ),
            "dsox_cycles": executor(
                "dsox_cycles"
            ),
            "save_result": executor(
                "save_result"
            ),
        },
    )

    result = runner.run(
        "job-success"
    )

    assert (
        result.state
        == JobState.SUCCEEDED
    )

    assert calls == [
        "fsw_spectrum",
        "dsox_delay",
        "dsox_cycles",
        "save_result",
    ]

    assert all(
        step.state
        == StepState.SUCCEEDED
        for step in result.steps
    )


def test_known_failure_skips_remaining_steps():
    def ok(execution):
        pass

    def fail(execution):
        raise InstrumentCommunicationError(
            "measurement failed"
        )

    runner = SequentialWorkflowRunner(
        steps=make_steps(),
        executors={
            "fsw_spectrum": ok,
            "dsox_delay": fail,
            "dsox_cycles": ok,
            "save_result": ok,
        },
    )

    result = runner.run(
        "job-failed"
    )

    assert (
        result.state
        == JobState.FAILED
    )

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


def test_workflow_retry():
    attempts = {
        "count": 0
    }

    def unstable(execution):
        attempts["count"] += 1

        if attempts["count"] < 2:
            raise InstrumentCommunicationError(
                "temporary error"
            )

    runner = SequentialWorkflowRunner(
        steps=(
            CaptureStepDefinition(
                "unstable_step",
                max_retries=1,
            ),
        ),
        executors={
            "unstable_step": unstable,
        },
    )

    result = runner.run(
        "job-retry"
    )

    assert (
        result.state
        == JobState.SUCCEEDED
    )

    assert attempts["count"] == 2

    assert (
        result.steps[0]
        .metadata["attempts"]
        == 2
    )


def test_cancel_before_step():
    runner = SequentialWorkflowRunner(
        steps=make_steps(),
        executors={
            step.name: (
                lambda execution: None
            )
            for step in make_steps()
        },
        cancel_check=lambda: True,
    )

    result = runner.run(
        "job-canceled"
    )

    assert (
        result.state
        == JobState.CANCELED
    )

    assert (
        result.steps[0].state
        == StepState.CANCELED
    )

    assert all(
        step.state
        == StepState.SKIPPED
        for step in result.steps[1:]
    )


def test_executor_can_cancel_job():
    def cancel(execution):
        raise CaptureCanceledError(
            "user canceled"
        )

    runner = SequentialWorkflowRunner(
        steps=make_steps(),
        executors={
            "fsw_spectrum": cancel,
            "dsox_delay": (
                lambda execution: None
            ),
            "dsox_cycles": (
                lambda execution: None
            ),
            "save_result": (
                lambda execution: None
            ),
        },
    )

    result = runner.run(
        "job-canceled"
    )

    assert (
        result.state
        == JobState.CANCELED
    )


def test_programming_error_is_not_swallowed():
    def bug(execution):
        raise TypeError(
            "programming bug"
        )

    runner = SequentialWorkflowRunner(
        steps=(
            CaptureStepDefinition(
                "bug"
            ),
        ),
        executors={
            "bug": bug,
        },
    )

    with pytest.raises(
        TypeError,
        match="programming bug",
    ):
        runner.run(
            "job-bug"
        )


def test_executor_receives_deadline():
    observed = {}

    def executor(execution):
        observed["has_deadline"] = (
            execution.has_deadline
        )

        observed["remaining_s"] = (
            execution.remaining_s
        )

    runner = SequentialWorkflowRunner(
        steps=(
            CaptureStepDefinition(
                "timed",
                timeout_s=1.0,
            ),
        ),
        executors={
            "timed": executor,
        },
    )

    result = runner.run(
        "job-deadline"
    )

    assert (
        result.state
        == JobState.SUCCEEDED
    )

    assert (
        observed["has_deadline"]
        is True
    )

    assert (
        observed["remaining_s"]
        is not None
    )

    assert (
        0.0
        < observed["remaining_s"]
        <= 1.0
    )


def test_timeout_marks_step_failed():
    def slow(execution):
        time.sleep(0.02)

    runner = SequentialWorkflowRunner(
        steps=(
            CaptureStepDefinition(
                "slow",
                timeout_s=0.01,
            ),
            CaptureStepDefinition(
                "never",
            ),
        ),
        executors={
            "slow": slow,
            "never": (
                lambda execution: None
            ),
        },
    )

    result = runner.run(
        "job-timeout"
    )

    assert (
        result.state
        == JobState.FAILED
    )

    assert (
        result.steps[0].state
        == StepState.FAILED
    )

    assert (
        result.steps[0]
        .metadata["error_type"]
        == "InstrumentTimeoutError"
    )

    assert (
        result.steps[0]
        .metadata["timeout_s"]
        == 0.01
    )

    assert (
        result.steps[1].state
        == StepState.SKIPPED
    )


def test_executor_can_observe_runtime_cancel_signal():
    state = {
        "canceled": False,
    }

    observed = []

    def executor(execution):
        assert execution.canceled is False

        state["canceled"] = True

        observed.append(
            execution.canceled
        )

        if execution.canceled:
            raise CaptureCanceledError(
                "runtime cancellation"
            )

    runner = SequentialWorkflowRunner(
        steps=(
            CaptureStepDefinition(
                "running_step",
            ),
            CaptureStepDefinition(
                "never",
            ),
        ),
        executors={
            "running_step": executor,
            "never": (
                lambda execution: None
            ),
        },
        cancel_check=(
            lambda: state["canceled"]
        ),
    )

    result = runner.run(
        "job-runtime-cancel"
    )

    assert observed == [True]

    assert (
        result.state
        == JobState.CANCELED
    )

    assert (
        result.steps[0].state
        == StepState.CANCELED
    )

    assert (
        result.steps[1].state
        == StepState.SKIPPED
    )
