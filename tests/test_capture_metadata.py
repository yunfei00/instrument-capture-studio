from datetime import datetime

from instrument_capture_studio.core.results import SpectrumResult, WaveformResult
from instrument_capture_studio.data.metadata import (
    build_capture_metadata,
    load_capture_metadata,
    write_capture_metadata,
)
from instrument_capture_studio.workflows.context import CaptureContext


def _spectrum(level: float) -> SpectrumResult:
    return SpectrumResult(
        frequencies_hz=[500e6, 600e6, 700e6],
        amplitudes_dbm=[level, level + 1.0, level + 2.0],
        metadata={"rbw_hz": 1e6},
    )


def _waveform(kind: str, scale: float, level: float, position: float) -> WaveformResult:
    return WaveformResult(
        channel="CH1",
        time_s=[0.0, 1e-6],
        voltage_v=[level, level + 0.1],
        sample_rate_hz=1e6,
        metadata={
            "raw_points": 2,
            "sample_kind": kind,
            "timebase_scale_s": scale,
            "horizontal_position_s": position,
        },
    )


def make_complete_context() -> CaptureContext:
    return CaptureContext(
        spectrum_ext=_spectrum(-80.0),
        spectrum_freerun=_spectrum(-70.0),
        waveform_sync=_waveform("sync", 2e-6, 0.1, 1e-5),
        waveform_followup=_waveform("followup", 20e-9, 0.5, 0.484),
        metadata={
            "recipe": "ext_imm_pair",
            "operator_note": "test",
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


def test_build_capture_metadata():
    context = make_complete_context()
    metadata = build_capture_metadata(
        "job-001",
        context,
        captured_at=datetime(2026, 8, 28, 16, 45, 0),
    )

    assert metadata["schema_version"] == 1
    assert metadata["job_id"] == "job-001"
    assert metadata["captured_at"] == "2026-08-28T16:45:00"
    assert metadata["recipe"] == "ext_imm_pair"
    assert metadata["capture_complete"] is True

    assert metadata["spectra"]["ext"]["points"] == 3
    assert metadata["spectra"]["ext"]["start_frequency_hz"] == 500e6
    assert metadata["spectra"]["ext"]["stop_frequency_hz"] == 700e6
    assert metadata["spectra"]["freerun"]["points"] == 3

    osc = metadata["oscilloscope"]
    assert osc["waveform_channel"] == "CH1"
    assert osc["sync"]["points"] == 2
    assert osc["sync"]["metadata"]["sample_kind"] == "sync"
    assert osc["followup"]["points"] == 2
    assert osc["followup"]["metadata"]["sample_kind"] == "followup"
    assert osc["timing_windows"]["followup"]["position_readback_s"] == 0.484


def test_metadata_supports_incomplete_context():
    metadata = build_capture_metadata(
        "job-incomplete",
        CaptureContext(metadata={"recipe": "ext_imm_pair"}),
    )

    assert metadata["schema_version"] == 1
    assert metadata["capture_complete"] is False
    assert metadata["spectra"]["ext"] is None
    assert metadata["spectra"]["freerun"] is None
    assert metadata["oscilloscope"]["sync"] is None
    assert metadata["oscilloscope"]["followup"] is None


def test_metadata_write_and_reload(tmp_path):
    metadata = build_capture_metadata(
        "job-reload",
        make_complete_context(),
        captured_at=datetime(2026, 8, 28, 16, 45, 0),
    )
    path = tmp_path / "metadata.json"
    write_capture_metadata(path, metadata)
    assert path.is_file()
    loaded = load_capture_metadata(path)
    assert loaded == metadata
