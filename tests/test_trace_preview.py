import json

import numpy as np

from instrument_capture_studio.data.trace_preview import load_trace_preview


def test_loads_spectrum_preview_and_downsamples(tmp_path):
    path = tmp_path / "spectrum.npz"
    np.savez_compressed(
        path,
        frequency_hz=np.linspace(700e6, 800e6, 10001),
        amplitude_dbm=np.linspace(-90.0, -30.0, 10001),
    )

    preview = load_trace_preview(path, max_points=1000)

    assert preview.title == "Spectrum"
    assert preview.x_label == "Frequency (MHz)"
    assert preview.y_label == "Amplitude (dBm)"
    assert len(preview.x) == 1000
    assert preview.x[0] == 700.0
    assert preview.x[-1] == 800.0


def test_loads_zero_span_spectrum_preview_on_time_axis(tmp_path):
    path = tmp_path / "spectrum_ext.npz"
    np.savez_compressed(
        path,
        frequency_hz=np.array([700e6, 700e6, 700e6]),
        time_s=np.array([0.0, 0.1, 0.2]),
        amplitude_dbm=np.array([-80.0, -60.0, -70.0]),
        center_frequency_hz=np.array(700e6),
        span_hz=np.array(0.0),
        sweep_time_s=np.array(0.2),
    )

    preview = load_trace_preview(path)

    assert preview.title == "Spectrum EXT"
    assert preview.x_label == "Time (ms)"
    assert preview.x.tolist() == [0.0, 100.0, 200.0]
    assert preview.y.tolist() == [-80.0, -60.0, -70.0]
    assert "Center 700 MHz" in preview.details
    assert "Sweep Time 0.2 s" in preview.details


def test_reconstructs_legacy_zero_span_from_metadata(tmp_path):
    path = tmp_path / "spectrum_freerun.npz"
    np.savez_compressed(
        path,
        frequency_hz=np.array([700e6, 700e6, 700e6]),
        amplitude_dbm=np.array([-80.0, -60.0, -70.0]),
    )
    (tmp_path / "metadata.json").write_text(
        json.dumps({"metadata": {"fsw_sweep_time_s": 0.4}}),
        encoding="utf-8",
    )

    preview = load_trace_preview(path)

    assert preview.x_label == "Time (ms)"
    assert preview.x.tolist() == [0.0, 200.0, 400.0]
    assert "Legacy Zero Span · reconstructed from metadata" in preview.details


def test_legacy_zero_span_without_sweep_time_uses_trace_point(tmp_path):
    path = tmp_path / "spectrum_imm.npz"
    np.savez_compressed(
        path,
        frequency_hz=np.array([700e6, 700e6, 700e6]),
        amplitude_dbm=np.array([-80.0, -60.0, -70.0]),
    )

    preview = load_trace_preview(path)

    assert preview.x_label == "Trace point"
    assert preview.x.tolist() == [0.0, 1.0, 2.0]
    assert "Legacy Zero Span · Sweep Time unavailable" in preview.details


def test_loads_waveform_preview(tmp_path):
    path = tmp_path / "waveform.npz"
    np.savez_compressed(
        path,
        time_s=np.array([0.0, 1e-6, 2e-6]),
        voltage_v=np.array([0.0, 1.0, 0.0]),
    )

    preview = load_trace_preview(path)

    assert preview.title == "Waveform"
    assert preview.x_label == "Time (µs)"
    assert preview.y_label == "Voltage (V)"
    assert preview.x.tolist() == [0.0, 1.0, 2.0]
    assert preview.y.tolist() == [0.0, 1.0, 0.0]


def test_formal_recipe_filenames_get_distinct_titles(tmp_path):
    spectrum_ext = tmp_path / "spectrum_ext.npz"
    spectrum_freerun = tmp_path / "spectrum_freerun.npz"
    waveform_sync = tmp_path / "waveform_sync.npz"
    waveform_followup = tmp_path / "waveform_followup.npz"

    for path in (spectrum_ext, spectrum_freerun):
        np.savez_compressed(
            path,
            frequency_hz=np.array([700e6, 701e6]),
            amplitude_dbm=np.array([-60.0, -50.0]),
        )
    for path in (waveform_sync, waveform_followup):
        np.savez_compressed(
            path,
            time_s=np.array([0.0, 1e-6]),
            voltage_v=np.array([0.0, 1.0]),
        )

    assert load_trace_preview(spectrum_ext).title == "Spectrum EXT"
    assert load_trace_preview(spectrum_freerun).title == "Spectrum Free Run"
    assert load_trace_preview(waveform_sync).title == "Waveform Sync"
    assert load_trace_preview(waveform_followup).title == "Waveform Follow-up"
