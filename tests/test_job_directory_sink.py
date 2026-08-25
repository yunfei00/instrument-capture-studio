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

    spectrum_npz_path = (
        root
        / "spectrum.npz"
    )

    assert metadata_path.is_file()
    assert spectrum_path.is_file()
    assert spectrum_npz_path.is_file()

    assert output_files == (
        str(metadata_path),
        str(spectrum_path),
        str(spectrum_npz_path),
    )

    lines = spectrum_path.read_text(
        encoding="utf-8"
    ).splitlines()

    assert lines == [
        "frequency_hz,amplitude_dbm",
        "500000000.0,-80.0",
        "600000000.0,-40.0",
    ]


def test_job_directory_sink_writes_waveform_csv(
    tmp_path,
):
    from instrument_capture_studio.core.results import (
        WaveformResult,
    )

    sink = JobDirectoryResultSink(
        tmp_path,
        clock=fixed_clock,
    )

    context = CaptureContext(
        waveform=WaveformResult(
            channel="CH1",
            time_s=[
                0.0,
                1e-6,
            ],
            voltage_v=[
                0.1,
                0.2,
            ],
            sample_rate_hz=1e6,
        )
    )

    output_files = sink.save(
        "job-waveform",
        context,
    )

    root = (
        tmp_path
        / "2026-08-25"
        / "job-waveform"
    )

    metadata_path = (
        root
        / "metadata.json"
    )

    waveform_path = (
        root
        / "waveform.csv"
    )

    waveform_npz_path = (
        root
        / "waveform.npz"
    )

    assert metadata_path.is_file()
    assert waveform_path.is_file()
    assert waveform_npz_path.is_file()

    assert output_files == (
        str(metadata_path),
        str(waveform_path),
        str(waveform_npz_path),
    )

    lines = waveform_path.read_text(
        encoding="utf-8"
    ).splitlines()

    assert lines == [
        "time_s,voltage_v",
        "0.0,0.1",
        "1e-06,0.2",
    ]


def test_job_directory_sink_writes_complete_data_set(
    tmp_path,
):
    from instrument_capture_studio.core.results import (
        SpectrumResult,
        WaveformResult,
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
        ),
        waveform=WaveformResult(
            channel="CH1",
            time_s=[
                0.0,
                1e-6,
            ],
            voltage_v=[
                0.1,
                0.2,
            ],
            sample_rate_hz=1e6,
        ),
    )

    output_files = sink.save(
        "job-complete-data",
        context,
    )

    root = (
        tmp_path
        / "2026-08-25"
        / "job-complete-data"
    )

    expected = (
        root / "metadata.json",
        root / "spectrum.csv",
        root / "spectrum.npz",
        root / "waveform.csv",
        root / "waveform.npz",
    )

    assert all(
        path.is_file()
        for path in expected
    )

    assert output_files == tuple(
        str(path)
        for path in expected
    )


def test_job_directory_sink_writes_job_manifest(
    tmp_path,
):
    from datetime import (
        datetime,
        timezone,
    )

    from instrument_capture_studio.core.models import (
        CaptureResult,
        JobState,
    )
    from instrument_capture_studio.data.job_manifest import (
        load_job_manifest,
    )

    sink = JobDirectoryResultSink(
        tmp_path,
    )

    result = CaptureResult(
        job_id="job-manifest",
        state=JobState.FAILED,
        started_at=datetime(
            2026,
            8,
            25,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        finished_at=datetime(
            2026,
            8,
            25,
            9,
            0,
            5,
            tzinfo=timezone.utc,
        ),
    )

    path = sink.save_job(
        result
    )

    manifest_path = (
        tmp_path
        / "2026-08-25"
        / "job-manifest"
        / "job.json"
    )

    assert path == str(
        manifest_path
    )

    assert manifest_path.is_file()

    manifest = load_job_manifest(
        manifest_path
    )

    assert manifest[
        "job_id"
    ] == "job-manifest"

    assert manifest[
        "state"
    ] == "failed"
