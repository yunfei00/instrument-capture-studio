from datetime import datetime, timezone

import pytest

from instrument_capture_studio.core.models import (
    CaptureResult,
    JobState,
    StepResult,
    StepState,
)
from instrument_capture_studio.data.job_manifest import (
    build_job_manifest,
    load_job_manifest,
    write_job_manifest,
)


STARTED = datetime(
    2026,
    8,
    25,
    9,
    0,
    0,
    tzinfo=timezone.utc,
)

FINISHED = datetime(
    2026,
    8,
    25,
    9,
    0,
    5,
    tzinfo=timezone.utc,
)


def test_build_success_job_manifest():
    result = CaptureResult(
        job_id="job-success",
        state=JobState.SUCCEEDED,
        started_at=STARTED,
        finished_at=FINISHED,
        steps=[
            StepResult(
                name="fsw_spectrum",
                state=StepState.SUCCEEDED,
                started_at=STARTED,
                finished_at=FINISHED,
                metadata={
                    "attempts": 1,
                },
            ),
        ],
        output_files=[
            "metadata.json",
            "spectrum.npz",
        ],
        metadata={
            "capture_complete": True,
        },
    )

    manifest = build_job_manifest(
        result
    )

    assert manifest[
        "schema_version"
    ] == 1

    assert manifest[
        "job_id"
    ] == "job-success"

    assert manifest[
        "state"
    ] == "succeeded"

    assert manifest[
        "started_at"
    ] == STARTED.isoformat()

    assert manifest[
        "finished_at"
    ] == FINISHED.isoformat()

    assert manifest[
        "steps"
    ][0]["state"] == "succeeded"

    assert manifest[
        "output_files"
    ] == [
        "metadata.json",
        "spectrum.npz",
    ]


def test_build_failed_job_manifest_keeps_error():
    result = CaptureResult(
        job_id="job-failed",
        state=JobState.FAILED,
        started_at=STARTED,
        finished_at=FINISHED,
        steps=[
            StepResult(
                name="fsw_spectrum",
                state=StepState.FAILED,
                started_at=STARTED,
                finished_at=FINISHED,
                error="measurement timeout",
                metadata={
                    "error_type": (
                        "InstrumentTimeoutError"
                    ),
                    "attempts": 1,
                },
            ),
            StepResult(
                name="dsox_delay",
                state=StepState.SKIPPED,
            ),
        ],
    )

    manifest = build_job_manifest(
        result
    )

    assert manifest[
        "state"
    ] == "failed"

    assert manifest[
        "steps"
    ][0]["error"] == (
        "measurement timeout"
    )

    assert manifest[
        "steps"
    ][0]["metadata"][
        "error_type"
    ] == "InstrumentTimeoutError"

    assert manifest[
        "steps"
    ][1]["state"] == "skipped"


def test_build_canceled_job_manifest():
    result = CaptureResult(
        job_id="job-canceled",
        state=JobState.CANCELED,
        started_at=STARTED,
        finished_at=FINISHED,
        steps=[
            StepResult(
                name="fsw_spectrum",
                state=StepState.CANCELED,
                error="measurement canceled",
            ),
        ],
    )

    manifest = build_job_manifest(
        result
    )

    assert manifest[
        "state"
    ] == "canceled"

    assert manifest[
        "steps"
    ][0]["state"] == "canceled"

    assert manifest[
        "steps"
    ][0]["error"] == (
        "measurement canceled"
    )


def test_job_manifest_write_and_reload(
    tmp_path,
):
    result = CaptureResult(
        job_id="job-reload",
        state=JobState.SUCCEEDED,
        started_at=STARTED,
        finished_at=FINISHED,
    )

    manifest = build_job_manifest(
        result
    )

    path = (
        tmp_path
        / "job.json"
    )

    write_job_manifest(
        path,
        manifest,
    )

    assert path.is_file()

    loaded = load_job_manifest(
        path
    )

    assert loaded == manifest
