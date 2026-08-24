import pytest

from instrument_capture_studio.workflows.base import CaptureStepDefinition


def test_step_definition():
    step = CaptureStepDefinition(
        name="fsw_spectrum",
        timeout_s=10,
        max_retries=2,
    )

    assert step.name == "fsw_spectrum"
    assert step.timeout_s == 10
    assert step.max_retries == 2


def test_empty_step_name_is_invalid():
    with pytest.raises(ValueError):
        CaptureStepDefinition(name="")


def test_invalid_timeout_is_rejected():
    with pytest.raises(ValueError):
        CaptureStepDefinition(
            name="test",
            timeout_s=0,
        )


def test_negative_retries_are_rejected():
    with pytest.raises(ValueError):
        CaptureStepDefinition(
            name="test",
            max_retries=-1,
        )
