from datetime import datetime

from instrument_capture_studio.core.results import (
    MeasurementResult,
    SpectrumResult,
    WaveformResult,
)
from instrument_capture_studio.data.job_loader import load_capture_job
from instrument_capture_studio.data.job_sink import JobDirectoryResultSink
from instrument_capture_studio.data.metadata import build_capture_metadata
from instrument_capture_studio.workflows.context import CaptureContext


def _spectrum(level):
    return SpectrumResult(
        frequencies_hz=[700e6, 705e6, 710e6],
        amplitudes_dbm=[level, level + 1, level + 2],
        metadata={"rbw_hz": 1e6},
    )


def _waveform(level, kind, scale):
    return WaveformResult(
        channel="CH1",
        time_s=[0.0, 1e-9],
        voltage_v=[level, level + 0.1],
        sample_rate_hz=1e9,
        metadata={
            "raw_points": 2,
            "sample_kind": kind,
            "timebase_scale_s": scale,
        },
    )


def _paired_context():
    return CaptureContext(
        spectrum_ext=_spectrum(-60.0),
        spectrum_imm=_spectrum(-70.0),
        delay=MeasurementResult(
            "DELAY",
            1.2e-6,
            "s",
            {"timebase_scale_s": 5e-7},
        ),
        cycle_count=MeasurementResult(
            "CYCLE_COUNT",
            3.0,
            "count",
            {"timebase_scale_s": 1e-4},
        ),
        waveform_delay=_waveform(0.1, "delay", 5e-7),
        waveform_cycle=_waveform(0.5, "cycle_count", 1e-4),
        metadata={
            "recipe": "ext_imm_pair",
            "waveform_channel": "CH1",
            "delay_timebase_scale_s": 5e-7,
            "cycle_timebase_scale_s": 1e-4,
        },
    )


def test_formal_metadata_explicitly_separates_all_four_traces():
    metadata = build_capture_metadata(
        "job-pair",
        _paired_context(),
        captured_at=datetime(2026, 8, 27, 11, 0, 0),
    )

    assert metadata["schema_version"] == 1
    assert metadata["capture_complete"] is True
    assert metadata["recipe"] == "ext_imm_pair"
    assert metadata["spectra"]["ext"]["points"] == 3
    assert metadata["spectra"]["imm"]["points"] == 3
    assert metadata["oscilloscope"]["delay"]["waveform"]["channel"] == "CH1"
    assert (
        metadata["oscilloscope"]["delay"]["waveform"]["metadata"]
        ["timebase_scale_s"]
        == 5e-7
    )
    assert (
        metadata["oscilloscope"]["cycle_count"]["waveform"]["metadata"]
        ["timebase_scale_s"]
        == 1e-4
    )


def test_formal_paired_sink_and_loader_round_trip(tmp_path):
    captured_at = datetime(2026, 8, 27, 11, 0, 0)
    sink = JobDirectoryResultSink(tmp_path, clock=lambda: captured_at)
    sink.begin_job("job-pair", captured_at)

    outputs = sink.save("job-pair", _paired_context())
    job_dir = tmp_path / "2026-08-27" / "job-pair"

    expected = {
        "metadata.json",
        "spectrum_ext.csv",
        "spectrum_ext.npz",
        "spectrum_imm.csv",
        "spectrum_imm.npz",
        "waveform_delay.csv",
        "waveform_delay.npz",
        "waveform_cycle.csv",
        "waveform_cycle.npz",
    }
    assert {path.name for path in job_dir.iterdir()} == expected
    assert {path.split("\\")[-1].split("/")[-1] for path in outputs} == expected

    loaded = load_capture_job(job_dir)
    assert loaded.metadata["schema_version"] == 1
    assert loaded.context.is_paired_complete is True
    assert loaded.context.spectrum_ext.amplitudes_dbm == [-60.0, -59.0, -58.0]
    assert loaded.context.spectrum_imm.amplitudes_dbm == [-70.0, -69.0, -68.0]
    assert loaded.context.waveform_delay.voltage_v == [0.1, 0.2]
    assert loaded.context.waveform_cycle.voltage_v == [0.5, 0.6]
    assert loaded.context.waveform_delay.metadata["sample_kind"] == "delay"
    assert loaded.context.waveform_cycle.metadata["sample_kind"] == "cycle_count"


def test_partial_pair_is_not_complete():
    context = CaptureContext(
        spectrum_ext=_spectrum(-60.0),
        metadata={"recipe": "ext_imm_pair"},
    )
    metadata = build_capture_metadata("job-partial", context)

    assert metadata["schema_version"] == 1
    assert metadata["capture_complete"] is False
    assert metadata["spectra"]["ext"] is not None
    assert metadata["spectra"]["imm"] is None
