import pytest

from instrument_capture_studio.app.recovery import (
    RecoveryPolicy,
    recovery_reason_from_exception,
    recovery_reason_from_result,
)
from instrument_capture_studio.core.exceptions import (
    InstrumentCommunicationError,
    InstrumentConnectionError,
    InstrumentTimeoutError,
)
from instrument_capture_studio.core.models import (
    CaptureResult,
    JobState,
    StepResult,
    StepState,
)


def test_recovery_policy_defaults():
    policy = RecoveryPolicy()

    assert policy.max_attempts == 3
    assert policy.reconnect_delay_s == 2.0
    assert policy.can_retry(1) is True
    assert policy.can_retry(2) is True
    assert policy.can_retry(3) is False


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_attempts": 0}, "max_attempts"),
        ({"reconnect_delay_s": -1}, "reconnect_delay_s"),
    ],
)
def test_recovery_policy_rejects_invalid_values(kwargs, message):
    with pytest.raises(ValueError, match=message):
        RecoveryPolicy(**kwargs)


@pytest.mark.parametrize(
    "exc",
    [
        InstrumentConnectionError("connect failed"),
        InstrumentCommunicationError("transport failed"),
    ],
)
def test_recovery_accepts_connection_and_communication_exceptions(exc):
    reason = recovery_reason_from_exception(exc)

    assert reason is not None
    assert reason.error_type == type(exc).__name__
    assert reason.stage == "application"


def test_recovery_does_not_retry_measurement_timeout_exception():
    reason = recovery_reason_from_exception(
        InstrumentTimeoutError("trigger timeout")
    )

    assert reason is None


def test_recovery_accepts_failed_communication_step():
    result = CaptureResult(
        job_id="job-recover",
        state=JobState.FAILED,
        steps=[
            StepResult(
                name="dsox_waveform",
                state=StepState.FAILED,
                error="read waveform: link lost",
                metadata={
                    "error_type": "InstrumentCommunicationError",
                },
            )
        ],
    )

    reason = recovery_reason_from_result(result)

    assert reason is not None
    assert reason.stage == "dsox_waveform"
    assert reason.error_type == "InstrumentCommunicationError"


def test_recovery_does_not_retry_timeout_result():
    result = CaptureResult(
        job_id="job-timeout",
        state=JobState.FAILED,
        steps=[
            StepResult(
                name="fsw_spectrum",
                state=StepState.FAILED,
                error="measurement timeout",
                metadata={
                    "error_type": "InstrumentTimeoutError",
                },
            )
        ],
    )

    assert recovery_reason_from_result(result) is None


def test_recovery_does_not_retry_success_or_cancel():
    success = CaptureResult(
        job_id="job-success",
        state=JobState.SUCCEEDED,
    )
    canceled = CaptureResult(
        job_id="job-canceled",
        state=JobState.CANCELED,
    )

    assert recovery_reason_from_result(success) is None
    assert recovery_reason_from_result(canceled) is None
