import numpy as np
import pytest

from instrument_capture_studio.core.results import SpectrumResult, WaveformResult
from instrument_capture_studio.data.npz import (
    load_spectrum_npz,
    write_spectrum_npz,
    write_waveform_npz,
)


def test_write_and_reload_spectrum_npz(tmp_path):
    path = tmp_path / "spectrum.npz"
    spectrum = SpectrumResult(
        frequencies_hz=[500e6, 600e6, 700e6],
        amplitudes_dbm=[-80.0, -40.5, -70.25],
    )

    write_spectrum_npz(path, spectrum)

    assert path.is_file()
    with np.load(path, allow_pickle=False) as data:
        assert set(data.files) == {"frequency_hz", "amplitude_dbm"}
        np.testing.assert_allclose(data["frequency_hz"], spectrum.frequencies_hz)
        np.testing.assert_allclose(data["amplitude_dbm"], spectrum.amplitudes_dbm)


def test_write_and_reload_zero_span_spectrum_npz(tmp_path):
    path = tmp_path / "spectrum_zero_span.npz"
    spectrum = SpectrumResult(
        frequencies_hz=[700e6, 700e6, 700e6],
        amplitudes_dbm=[-80.0, -40.5, -70.25],
        time_s=[0.0, 0.1, 0.2],
        metadata={
            "axis_kind": "time",
            "center_frequency_hz": 700e6,
            "span_hz": 0.0,
            "sweep_time_s": 0.2,
        },
    )

    write_spectrum_npz(path, spectrum)

    with np.load(path, allow_pickle=False) as data:
        assert {
            "frequency_hz",
            "amplitude_dbm",
            "time_s",
            "center_frequency_hz",
            "span_hz",
            "sweep_time_s",
            "metadata_json",
        } == set(data.files)
        np.testing.assert_allclose(data["time_s"], spectrum.time_s)
        assert float(data["center_frequency_hz"]) == 700e6
        assert float(data["sweep_time_s"]) == pytest.approx(0.2)

    loaded = load_spectrum_npz(path)
    assert loaded.axis_kind == "time"
    assert loaded.time_s == pytest.approx([0.0, 0.1, 0.2])
    assert loaded.metadata["center_frequency_hz"] == 700e6
    assert loaded.metadata["sweep_time_s"] == pytest.approx(0.2)


def test_spectrum_npz_embeds_and_restores_video_trigger_metadata(tmp_path):
    path = tmp_path / "spectrum_video.npz"
    spectrum = SpectrumResult(
        frequencies_hz=[700e6],
        amplitudes_dbm=[-48.0],
        metadata={
            "trigger_source": "VID",
            "video_trigger": {
                "video_level_pct_requested": 45.9,
                "trigger_offset_s_requested": -0.005,
            },
        },
    )

    write_spectrum_npz(path, spectrum)
    loaded = load_spectrum_npz(path)

    assert loaded.metadata["trigger_source"] == "VID"
    assert loaded.metadata["video_trigger"]["video_level_pct_requested"] == 45.9
    assert loaded.metadata["video_trigger"]["trigger_offset_s_requested"] == -0.005


def test_spectrum_npz_rejects_mismatched_lengths(tmp_path):
    spectrum = SpectrumResult(
        frequencies_hz=[1.0, 2.0],
        amplitudes_dbm=[-10.0],
    )

    with pytest.raises(ValueError, match="lengths must match"):
        write_spectrum_npz(tmp_path / "spectrum.npz", spectrum)


def test_write_and_reload_waveform_npz(tmp_path):
    path = tmp_path / "waveform.npz"
    waveform = WaveformResult(
        channel="CH1",
        time_s=[0.0, 1e-6, 2e-6],
        voltage_v=[0.1, 0.2, -0.1],
        sample_rate_hz=1e6,
    )

    write_waveform_npz(path, waveform)

    assert path.is_file()
    with np.load(path, allow_pickle=False) as data:
        assert set(data.files) == {"time_s", "voltage_v"}
        np.testing.assert_allclose(data["time_s"], waveform.time_s)
        np.testing.assert_allclose(data["voltage_v"], waveform.voltage_v)


def test_waveform_npz_rejects_mismatched_lengths(tmp_path):
    waveform = WaveformResult(
        channel="CH1",
        time_s=[0.0, 1e-6],
        voltage_v=[0.1],
    )

    with pytest.raises(ValueError, match="lengths must match"):
        write_waveform_npz(tmp_path / "waveform.npz", waveform)
