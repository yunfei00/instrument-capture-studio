"""Recovery policy for transient instrument connection failures."""

from dataclasses import dataclass

from instrument_capture_studio.core.exceptions import (
    InstrumentCommunicationError,
    InstrumentConnectionError,
)
from instrument_capture_studio.core.models import (
    CaptureResult,
    JobState,
    StepState,
)


@dataclass(frozen=True)
class RecoveryPolicy:
    """Automatic reconnect/retry policy for one GUI capture request."""

    max_attempts: int = 4
    reconnect_delay_s: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.reconnect_delay_s < 0:
            raise ValueError("reconnect_delay_s must not be negative")

    def can_retry(self, attempt: int) -> bool:
        return attempt < self.max_attempts


@dataclass(frozen=True)
class RecoveryReason:
    """Why an automatic reconnect/retry is allowed."""

    error_type: str
    message: str
    stage: str | None = None


_RECOVERABLE_RESULT_ERROR_TYPES = {
    "InstrumentConnectionError",
    "InstrumentCommunicationError",
}

# The real DSO-X installation is reached through a USB-to-TCP forwarding
# bridge. If the USB side disappears while the TCP bridge itself remains
# reachable, the bridge can surface the lost instrument as an I/O timeout
# rather than a socket/connection exception. Retrying these two physical
# waveform steps through a fresh session is therefore appropriate.
#
# Do NOT generalize this to FSW steps: an FSW EXT timeout is a valid trigger
# timeout and Phase 8 explicitly requires that it does not enter RECONNECTING.
_DSOX_BRIDGE_TIMEOUT_STEPS = {
    "dsox_delay_group",
    "dsox_cycle_group",
}


def recovery_reason_from_exception(
    exc: Exception,
) -> RecoveryReason | None:
    """Classify exceptions raised before a CaptureResult can be returned."""

    if isinstance(
        exc,
        (
            InstrumentConnectionError,
            InstrumentCommunicationError,
        ),
    ):
        return RecoveryReason(
            error_type=type(exc).__name__,
            message=str(exc),
            stage="application",
        )

    return None


def recovery_reason_from_result(
    result: CaptureResult,
) -> RecoveryReason | None:
    """Classify failed workflow results that are safe to retry from scratch."""

    if result.state is not JobState.FAILED:
        return None

    for step in result.steps:
        if step.state is not StepState.FAILED:
            continue

        error_type = step.metadata.get("error_type")
        if error_type in _RECOVERABLE_RESULT_ERROR_TYPES:
            return RecoveryReason(
                error_type=str(error_type),
                message=step.error or "instrument communication failed",
                stage=step.name,
            )

        if (
            error_type == "InstrumentTimeoutError"
            and step.name in _DSOX_BRIDGE_TIMEOUT_STEPS
        ):
            return RecoveryReason(
                error_type="InstrumentTimeoutError",
                message=(
                    step.error
                    or "DSO-X waveform operation timed out; retry with a fresh session"
                ),
                stage=step.name,
            )

        # Any other failed step is intentionally non-recoverable. In
        # particular FSW trigger/measurement timeouts stop here and must not
        # be reclassified as a transport reconnect event.
        return None

    application_error = result.metadata.get("application_error")
    if isinstance(application_error, dict):
        error_type = application_error.get("error_type")
        if error_type in _RECOVERABLE_RESULT_ERROR_TYPES:
            return RecoveryReason(
                error_type=str(error_type),
                message=str(application_error.get("message") or ""),
                stage=(
                    str(application_error.get("stage"))
                    if application_error.get("stage") is not None
                    else None
                ),
            )

    return None
