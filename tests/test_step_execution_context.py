import time

from instrument_capture_studio.workflows.execution import (
    StepExecutionContext,
)


def test_context_without_timeout_has_no_deadline():
    context = StepExecutionContext.from_timeout(
        None
    )

    assert context.has_deadline is False
    assert context.remaining_s is None
    assert context.expired is False


def test_context_with_timeout_has_remaining_time():
    context = StepExecutionContext.from_timeout(
        1.0
    )

    assert context.has_deadline is True

    remaining = context.remaining_s

    assert remaining is not None
    assert 0.0 < remaining <= 1.0

    assert context.expired is False


def test_context_eventually_expires():
    context = StepExecutionContext.from_timeout(
        0.01
    )

    time.sleep(0.02)

    assert context.expired is True
    assert context.remaining_s == 0.0


def test_context_observes_dynamic_cancellation():
    state = {
        "canceled": False,
    }

    context = StepExecutionContext.from_timeout(
        None,
        cancel_check=lambda: state["canceled"],
    )

    assert context.canceled is False

    state["canceled"] = True

    assert context.canceled is True
