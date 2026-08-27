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
from instrument_capture_studio.workflows.context import CaptureContext


def _spectrum(level: float) -> SpectrumResult:
    return SpectrumResult(
        frequencies_hz=[500e6, 600e6, 700e6],
        amplitudes_dbm=[level, level + 1.0, level + 2.0],
        metadata={"rbw_hz": 1e6},
    )


def _waveform(kind: str, scale: float, level: float) -> WaveformResult:
    return WaveformResult(
        channel="CH1",
        time_s=[0.0, 1e-6],
        voltage_v=[level, level + 0.1],
        sample_rate_hz=1e6,
        metadata={
            "raw_points": 2,
            "sample_kind": kind,
            "timebase_scale_s": scale,
        },
    )


def make_complete_context() -> CaptureContext:
    return CaptureContext(
        spectrum_ext=_spectrum(-80.0),
        spectrum_imm=_spectrum(-70.0),
        delay=MeasurementResult(
            measurement="DELAY",
            value=1.25e-6,
            unit="s",
            metadata={
                "source1": "CHANnel1",
                "source2": "CHANnel2",
                "timebase_scale_s": 5e-7,
            },
        ),
        cycle_count=MeasurementResult(
            measurement="CYCLE_COUNT",
            value=12.0,
            unit="count",
            metadata={
                "source": "CHANnel1",
                "timebase_scale_s": 1e-4,
            },
        ),
        waveform_delay=_waveform("delay", 5e-7, 0.1),
        waveform_cycle=_waveform("cycle_count", 1e-4, 0.5),
        metadata={
            "recipe": "ext_imm_pair",
            "operator_note": "test",
            "waveform_channel": "CH1",
        },
    )


def test_build_capture_metadata():
    context = make_complete_context()
    metadata = build_capture_metadata(
        "job-001",
        context,
        captured_at=datetime(2026, 8, 25, 16, 45, 0),
    )

    assert metadata["schema_version"] == 1
    assert metadata["job_id"] == "job-001"
    assert metadata["captured_at"] == "2026-08-25T16:45:00"
    assert metadata["recipe"] == "ext_imm_pair"
    assert metadata["capture_complete"] is True

    assert metadata["spectra"]["ext"]["points"] == 3
    assert metadata["spectra"]["ext"]["start_frequency_hz"] == 500e6
    assert metadata["spectra"]["ext"]["stop_frequency_hz"] == 700e6
    assert metadata["spectra"]["imm"]["points"] == 3

    osc = metadata["oscilloscope"]
    assert osc["waveform_channel"] == "CH1"
    assert osc["delay"]["measurement"]["value"] == 1.25e-6
    assert osc["delay"]["waveform"]["points"] == 2
    assert osc["delay"]["waveform"]["metadata"]["sample_kind"] == "delay"
    assert osc["cycle_count"]["measurement"]["value"] == 12.0
    assert osc["cycle_count"]["waveform"]["points"] == 2
    assert (
        osc["cycle_count"]["waveform"]["metadata"]["sample_kind"]
        == "cycle_count"
    )


def test_metadata_supports_incomplete_context():
    metadata = build_capture_metadata(
        "job-incomplete",
        CaptureContext(metadata={"recipe": "ext_imm_pair"}),
    )

    assert metadata["schema_version"] == 1
    assert metadata["capture_complete"] is False
    assert metadata["spectra"]["ext"] is None
    assert metadata["spectra"]["imm"] is None
    assert metadata["oscilloscope"]["delay"]["measurement"] is None
    assert metadata["oscilloscope"]["delay"]["waveform"] is None
    assert metadata["oscilloscope"]["cycle_count"]["measurement"] is None
    assert metadata["oscilloscope"]["cycle_count"]["waveform"] is None


def test_metadata_write_and_reload(tmp_path):
    metadata = build_capture_metadata(
        "job-reload",
        make_complete_context(),
        captured_at=datetime(2026, 8, 25, 16, 45, 0),
    )
    path = tmp_path / "metadata.json"
    write_capture_metadata(path, metadata)
    assert path.is_file()
    loaded = load_capture_metadata(path)
    assert loaded == metadata
