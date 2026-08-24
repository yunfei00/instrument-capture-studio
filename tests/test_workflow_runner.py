from instrument_capture_studio.core.models import JobState, StepState
from instrument_capture_studio.workflows.base import CaptureStepDefinition
from instrument_capture_studio.workflows.runner import SequentialWorkflowRunner


def make_steps():
    return (
        CaptureStepDefinition("fsw_spectrum"),
        CaptureStepDefinition("dsox_delay"),
        CaptureStepDefinition("dsox_cycles"),
        CaptureStepDefinition("save_result"),
    )


def test_workflow_success():
    calls = []

    def executor(name):
        def run():
            calls.append(name)
        return run

    runner = SequentialWorkflowRunner(
        steps=make_steps(),
        executors={
            "fsw_spectrum": executor("fsw_spectrum"),
            "dsox_delay": executor("dsox_delay"),
            "dsox_cycles": executor("dsox_cycles"),
            "save_result": executor("save_result"),
        },
    )

    result = runner.run("job-success")

    assert result.state == JobState.SUCCEEDED

    assert calls == [
        "fsw_spectrum",
        "dsox_delay",
        "dsox_cycles",
        "save_result",
    ]

    assert all(
        step.state == StepState.SUCCEEDED
        for step in result.steps
    )


def test_workflow_failure_skips_remaining_steps():
    def ok():
        pass

    def fail():
        raise RuntimeError("measurement failed")

    runner = SequentialWorkflowRunner(
        steps=make_steps(),
        executors={
            "fsw_spectrum": ok,
            "dsox_delay": fail,
            "dsox_cycles": ok,
            "save_result": ok,
        },
    )

    result = runner.run("job-failed")

    assert result.state == JobState.FAILED

    assert result.steps[0].state == StepState.SUCCEEDED
    assert result.steps[1].state == StepState.FAILED
    assert result.steps[2].state == StepState.SKIPPED
    assert result.steps[3].state == StepState.SKIPPED

    assert result.steps[1].error == "measurement failed"


def test_workflow_retry():
    attempts = {"count": 0}

    def unstable():
        attempts["count"] += 1

        if attempts["count"] < 2:
            raise RuntimeError("temporary error")

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

    result = runner.run("job-retry")

    assert result.state == JobState.SUCCEEDED
    assert attempts["count"] == 2
    assert result.steps[0].metadata["attempts"] == 2
