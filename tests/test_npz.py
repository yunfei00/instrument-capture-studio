import numpy as np
import pytest

from instrument_capture_studio.core.results import (
    SpectrumResult,
    WaveformResult,
)
from instrument_capture_studio.data.npz import (
    write_spectrum_npz,
    write_waveform_npz,
)


def test_write_and_reload_spectrum_npz(
    tmp_path,
):
    path = (
        tmp_path
        / "spectrum.npz"
    )

    spectrum = SpectrumResult(
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
    )

    write_spectrum_npz(
        path,
        spectrum,
    )

    assert path.is_file()

    with np.load(
        path,
        allow_pickle=False,
    ) as data:
        assert set(
            data.files
        ) == {
            "frequency_hz",
            "amplitude_dbm",
        }

        np.testing.assert_allclose(
            data["frequency_hz"],
            spectrum.frequencies_hz,
        )

        np.testing.assert_allclose(
            data["amplitude_dbm"],
            spectrum.amplitudes_dbm,
        )


def test_spectrum_npz_rejects_mismatched_lengths(
    tmp_path,
):
    spectrum = SpectrumResult(
        frequencies_hz=[
            1.0,
            2.0,
        ],
        amplitudes_dbm=[
            -10.0,
        ],
    )

    with pytest.raises(
        ValueError,
        match="lengths must match",
    ):
        write_spectrum_npz(
            tmp_path
            / "spectrum.npz",
            spectrum,
        )


def test_write_and_reload_waveform_npz(
    tmp_path,
):
    path = (
        tmp_path
        / "waveform.npz"
    )

    waveform = WaveformResult(
        channel="CH1",
        time_s=[
            0.0,
            1e-6,
            2e-6,
        ],
        voltage_v=[
            0.1,
            0.2,
            -0.1,
        ],
        sample_rate_hz=1e6,
    )

    write_waveform_npz(
        path,
        waveform,
    )

    assert path.is_file()

    with np.load(
        path,
        allow_pickle=False,
    ) as data:
        assert set(
            data.files
        ) == {
            "time_s",
            "voltage_v",
        }

        np.testing.assert_allclose(
            data["time_s"],
            waveform.time_s,
        )

        np.testing.assert_allclose(
            data["voltage_v"],
            waveform.voltage_v,
        )


def test_waveform_npz_rejects_mismatched_lengths(
    tmp_path,
):
    waveform = WaveformResult(
        channel="CH1",
        time_s=[
            0.0,
            1e-6,
        ],
        voltage_v=[
            0.1,
        ],
    )

    with pytest.raises(
        ValueError,
        match="lengths must match",
    ):
        write_waveform_npz(
            tmp_path
            / "waveform.npz",
            waveform,
        )
