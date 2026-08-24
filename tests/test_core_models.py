from instrument_capture_studio.core.models import (
    CaptureResult,
    InstrumentState,
    InstrumentStatus,
    JobState,
    StepResult,
    StepState,
)


def test_instrument_status_defaults():
    status = InstrumentStatus(
        name="DSO-X",
        address="TCPIP0::TEST::INSTR",
    )

    assert status.state == InstrumentState.DISCONNECTED
    assert status.model is None
    assert status.last_error is None


def test_capture_result_defaults():
    result = CaptureResult(
        job_id="job-001",
    )

    assert result.state == JobState.PENDING
    assert result.steps == []
    assert result.output_files == []


def test_step_result_defaults():
    result = StepResult(
        name="fsw_spectrum",
    )

    assert result.state == StepState.PENDING
    assert result.error is None
