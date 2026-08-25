from datetime import datetime

from instrument_capture_studio.data.job_sink import (
    JobDirectoryResultSink,
)
from instrument_capture_studio.data.metadata import (
    load_capture_metadata,
)
from instrument_capture_studio.workflows.context import (
    CaptureContext,
)


def fixed_clock():
    return datetime(
        2026,
        8,
        25,
        16,
        45,
        30,
    )


def test_job_directory_sink_writes_metadata(
    tmp_path,
):
    sink = JobDirectoryResultSink(
        tmp_path,
        clock=fixed_clock,
    )

    context = CaptureContext(
        metadata={
            "note": "phase5",
        }
    )

    output_files = sink.save(
        "job-001",
        context,
    )

    expected = (
        tmp_path
        / "2026-08-25"
        / "job-001"
        / "metadata.json"
    )

    assert expected.is_file()

    assert output_files == (
        str(expected),
    )

    metadata = load_capture_metadata(
        expected
    )

    assert metadata[
        "job_id"
    ] == "job-001"

    assert metadata[
        "captured_at"
    ] == "2026-08-25T16:45:30"

    assert metadata[
        "capture_complete"
    ] is False

    assert metadata[
        "metadata"
    ][
        "note"
    ] == "phase5"


def test_job_directory_sink_separates_jobs(
    tmp_path,
):
    sink = JobDirectoryResultSink(
        tmp_path,
        clock=fixed_clock,
    )

    sink.save(
        "job-a",
        CaptureContext(),
    )

    sink.save(
        "job-b",
        CaptureContext(),
    )

    assert (
        tmp_path
        / "2026-08-25"
        / "job-a"
        / "metadata.json"
    ).is_file()

    assert (
        tmp_path
        / "2026-08-25"
        / "job-b"
        / "metadata.json"
    ).is_file()


def test_job_directory_sink_writes_spectrum_csv(
    tmp_path,
):
    from instrument_capture_studio.core.results import (
        SpectrumResult,
    )

    sink = JobDirectoryResultSink(
        tmp_path,
        clock=fixed_clock,
    )

    context = CaptureContext(
        spectrum=SpectrumResult(
            frequencies_hz=[
                500e6,
                600e6,
            ],
            amplitudes_dbm=[
                -80.0,
                -40.0,
            ],
        )
    )

    output_files = sink.save(
        "job-spectrum",
        context,
    )

    root = (
        tmp_path
        / "2026-08-25"
        / "job-spectrum"
    )

    metadata_path = (
        root
        / "metadata.json"
    )

    spectrum_path = (
        root
        / "spectrum.csv"
    )

    assert metadata_path.is_file()
    assert spectrum_path.is_file()

    assert output_files == (
        str(metadata_path),
        str(spectrum_path),
    )

    lines = spectrum_path.read_text(
        encoding="utf-8"
    ).splitlines()

    assert lines == [
        "frequency_hz,amplitude_dbm",
        "500000000.0,-80.0",
        "600000000.0,-40.0",
    ]
