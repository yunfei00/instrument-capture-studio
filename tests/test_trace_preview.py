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
    spectrum_imm = tmp_path / "spectrum_imm.npz"
    waveform_delay = tmp_path / "waveform_delay.npz"
    waveform_cycle = tmp_path / "waveform_cycle.npz"

    for path in (spectrum_ext, spectrum_imm):
        np.savez_compressed(
            path,
            frequency_hz=np.array([700e6, 701e6]),
            amplitude_dbm=np.array([-60.0, -50.0]),
        )
    for path in (waveform_delay, waveform_cycle):
        np.savez_compressed(
            path,
            time_s=np.array([0.0, 1e-6]),
            voltage_v=np.array([0.0, 1.0]),
        )

    assert load_trace_preview(spectrum_ext).title == "Spectrum EXT"
    assert load_trace_preview(spectrum_imm).title == "Spectrum IMM"
    assert load_trace_preview(waveform_delay).title == "Waveform DELAY"
    assert load_trace_preview(waveform_cycle).title == "Waveform CYCLE_COUNT"
