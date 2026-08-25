from datetime import datetime

from instrument_capture_studio.core.results import (
    MeasurementResult,
    SpectrumResult,
    WaveformResult,
)
from instrument_capture_studio.data.metadata import (
    build_capture_metadata,
    load_capture_metadata,
    write_capture_metadata,
)
from instrument_capture_studio.workflows.context import (
    CaptureContext,
)


def make_complete_context():
    return CaptureContext(
        spectrum=SpectrumResult(
            frequencies_hz=[
                500e6,
                600e6,
                700e6,
            ],
            amplitudes_dbm=[
                -80.0,
                -40.0,
                -70.0,
            ],
            metadata={
                "rbw_hz": 1e6,
            },
        ),
        delay=MeasurementResult(
            measurement="DELAY",
            value=1.25e-6,
            unit="s",
            metadata={
                "source1": "CHANnel1",
                "source2": "CHANnel2",
            },
        ),
        cycle_count=MeasurementResult(
            measurement="CYCLE_COUNT",
            value=12.0,
            unit="count",
            metadata={
                "source": "CHANnel1",
            },
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
            metadata={
                "raw_points": 2,
            },
        ),
        metadata={
            "operator_note": "test",
        },
    )


def test_build_capture_metadata():
    context = make_complete_context()

    metadata = build_capture_metadata(
        "job-001",
        context,
        captured_at=datetime(
            2026,
            8,
            25,
            16,
            45,
            0,
        ),
    )

    assert metadata[
        "schema_version"
    ] == 1

    assert metadata[
        "job_id"
    ] == "job-001"

    assert metadata[
        "captured_at"
    ] == "2026-08-25T16:45:00"

    assert metadata[
        "capture_complete"
    ] is True

    assert metadata[
        "measurements"
    ][
        "delay"
    ][
        "value"
    ] == 1.25e-6

    assert metadata[
        "measurements"
    ][
        "cycle_count"
    ][
        "value"
    ] == 12.0

    assert metadata[
        "spectrum"
    ][
        "points"
    ] == 3

    assert metadata[
        "spectrum"
    ][
        "start_frequency_hz"
    ] == 500e6

    assert metadata[
        "spectrum"
    ][
        "stop_frequency_hz"
    ] == 700e6

    assert metadata[
        "waveform"
    ][
        "points"
    ] == 2

    assert metadata[
        "waveform"
    ][
        "sample_rate_hz"
    ] == 1e6


def test_metadata_supports_incomplete_context():
    metadata = build_capture_metadata(
        "job-incomplete",
        CaptureContext(),
    )

    assert metadata[
        "capture_complete"
    ] is False

    assert metadata[
        "measurements"
    ][
        "delay"
    ] is None

    assert metadata[
        "measurements"
    ][
        "cycle_count"
    ] is None

    assert metadata[
        "spectrum"
    ] is None

    assert metadata[
        "waveform"
    ] is None


def test_metadata_write_and_reload(
    tmp_path,
):
    metadata = build_capture_metadata(
        "job-reload",
        make_complete_context(),
        captured_at=datetime(
            2026,
            8,
            25,
            16,
            45,
            0,
        ),
    )

    path = (
        tmp_path
        / "metadata.json"
    )

    write_capture_metadata(
        path,
        metadata,
    )

    assert path.is_file()

    loaded = load_capture_metadata(
        path
    )

    assert loaded == metadata
