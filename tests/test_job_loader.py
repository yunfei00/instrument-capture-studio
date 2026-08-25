from datetime import datetime

import pytest

from instrument_capture_studio.core.results import (
    MeasurementResult,
    SpectrumResult,
    WaveformResult,
)
from instrument_capture_studio.data.job_loader import (
    load_capture_job,
)
from instrument_capture_studio.data.job_sink import (
    JobDirectoryResultSink,
)
from instrument_capture_studio.workflows.context import (
    CaptureContext,
)


def fixed_clock():
    return datetime(
        2026,
        8,
        25,
        17,
        15,
        30,
    )


def make_context():
    return CaptureContext(
        spectrum=SpectrumResult(
            frequencies_hz=[
                500e6,
                600e6,
                700e6,
            ],
            amplitudes_dbm=[
                -80.0,
                -40.5,
                -70.25,
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
            "operator_note": "reload-test",
        },
    )


def test_save_and_reload_complete_capture_job(
    tmp_path,
):
    sink = JobDirectoryResultSink(
        tmp_path,
        clock=fixed_clock,
    )

    original = make_context()

    sink.save(
        "job-reload",
        original,
    )

    job_directory = (
        tmp_path
        / "2026-08-25"
        / "job-reload"
    )

    loaded = load_capture_job(
        job_directory
    )

    assert loaded.job_id == "job-reload"

    assert loaded.captured_at == fixed_clock()

    context = loaded.context

    assert context.is_complete is True

    assert (
        context.spectrum.frequencies_hz
        == original.spectrum.frequencies_hz
    )

    assert (
        context.spectrum.amplitudes_dbm
        == original.spectrum.amplitudes_dbm
    )

    assert (
        context.spectrum.metadata
        == original.spectrum.metadata
    )

    assert (
        context.delay.value
        == original.delay.value
    )

    assert (
        context.cycle_count.value
        == original.cycle_count.value
    )

    assert (
        context.waveform.time_s
        == original.waveform.time_s
    )

    assert (
        context.waveform.voltage_v
        == original.waveform.voltage_v
    )

    assert (
        context.waveform.sample_rate_hz
        == original.waveform.sample_rate_hz
    )

    assert (
        context.metadata
        == original.metadata
    )


def test_loader_supports_metadata_only_job(
    tmp_path,
):
    sink = JobDirectoryResultSink(
        tmp_path,
        clock=fixed_clock,
    )

    sink.save(
        "job-empty",
        CaptureContext(),
    )

    loaded = load_capture_job(
        tmp_path
        / "2026-08-25"
        / "job-empty"
    )

    assert (
        loaded.context.is_complete
        is False
    )

    assert loaded.context.spectrum is None
    assert loaded.context.delay is None
    assert loaded.context.cycle_count is None
    assert loaded.context.waveform is None


def test_loader_rejects_unknown_schema(
    tmp_path,
):
    job_directory = (
        tmp_path
        / "job-invalid"
    )

    job_directory.mkdir()

    (
        job_directory
        / "metadata.json"
    ).write_text(
        '{"schema_version": 999}',
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="schema_version",
    ):
        load_capture_job(
            job_directory
        )
