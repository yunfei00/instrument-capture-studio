from datetime import datetime

from instrument_capture_studio.core.results import SpectrumResult, WaveformResult
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


def _waveform(level, kind, scale, position):
    return WaveformResult(
        channel="CH1",
        time_s=[0.0, 1e-9],
        voltage_v=[level, level + 0.1],
        sample_rate_hz=1e9,
        metadata={
            "raw_points": 2,
            "sample_kind": kind,
            "timebase_scale_s": scale,
            "horizontal_position_s": position,
        },
    )


def _paired_context():
    return CaptureContext(
        spectrum_ext=_spectrum(-60.0),
        spectrum_freerun=_spectrum(-70.0),
        waveform_sync=_waveform(0.1, "sync", 2e-6, 1e-5),
        waveform_followup=_waveform(0.5, "followup", 20e-9, 0.484),
        metadata={
            "recipe": "ext_imm_pair",
            "waveform_channel": "CH1",
            "fsw_sweep_time_s": 2e-5,
            "timing_windows": {
                "sync": {
                    "position_readback_s": 1e-5,
                    "scale_readback_s_per_div": 2e-6,
                },
                "followup": {
                    "position_readback_s": 0.484,
                    "scale_readback_s_per_div": 20e-9,
                },
            },
        },
    )


def test_formal_metadata_explicitly_separates_all_four_traces():
    metadata = build_capture_metadata(
        "job-pair",
        _paired_context(),
        captured_at=datetime(2026, 8, 28, 16, 0, 0),
    )

    assert metadata["schema_version"] == 1
    assert metadata["capture_complete"] is True
    assert metadata["recipe"] == "ext_imm_pair"
    assert metadata["spectra"]["ext"]["points"] == 3
    assert metadata["spectra"]["freerun"]["points"] == 3
    assert metadata["oscilloscope"]["sync"]["channel"] == "CH1"
    assert metadata["oscilloscope"]["sync"]["metadata"]["sample_kind"] == "sync"
    assert (
        metadata["oscilloscope"]["followup"]["metadata"]["horizontal_position_s"]
        == 0.484
    )
    assert metadata["metadata"]["fsw_sweep_time_s"] == 2e-5


def test_formal_paired_sink_and_loader_round_trip(tmp_path):
    captured_at = datetime(2026, 8, 28, 16, 0, 0)
    sink = JobDirectoryResultSink(tmp_path, clock=lambda: captured_at)
    sink.begin_job("job-pair", captured_at)

    outputs = sink.save("job-pair", _paired_context())
    job_dir = tmp_path / "2026-08-28" / "job-pair"

    expected = {
        "metadata.json",
        "spectrum_ext.csv",
        "spectrum_ext.npz",
        "waveform_sync.csv",
        "waveform_sync.npz",
        "waveform_followup.csv",
        "waveform_followup.npz",
        "spectrum_freerun.csv",
        "spectrum_freerun.npz",
    }
    assert {path.name for path in job_dir.iterdir()} == expected
    assert {path.split("\\")[-1].split("/")[-1] for path in outputs} == expected

    loaded = load_capture_job(job_dir)
    assert loaded.metadata["schema_version"] == 1
    assert loaded.context.is_paired_complete is True
    assert loaded.context.spectrum_ext.amplitudes_dbm == [-60.0, -59.0, -58.0]
    assert loaded.context.spectrum_freerun.amplitudes_dbm == [-70.0, -69.0, -68.0]
    assert loaded.context.waveform_sync.voltage_v == [0.1, 0.2]
    assert loaded.context.waveform_followup.voltage_v == [0.5, 0.6]
    assert loaded.context.waveform_sync.metadata["sample_kind"] == "sync"
    assert loaded.context.waveform_followup.metadata["sample_kind"] == "followup"


def test_partial_pair_is_not_complete():
    context = CaptureContext(
        spectrum_ext=_spectrum(-60.0),
        metadata={"recipe": "ext_imm_pair"},
    )
    metadata = build_capture_metadata("job-partial", context)

    assert metadata["schema_version"] == 1
    assert metadata["capture_complete"] is False
    assert metadata["spectra"]["ext"] is not None
    assert metadata["spectra"]["freerun"] is None
    assert metadata["oscilloscope"]["sync"] is None
    assert metadata["oscilloscope"]["followup"] is None
