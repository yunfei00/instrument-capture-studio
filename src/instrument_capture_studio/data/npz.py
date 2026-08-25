from pathlib import Path

import numpy as np

from instrument_capture_studio.core.results import (
    SpectrumResult,
    WaveformResult,
)


def _write_arrays(
    path: Path,
    **arrays,
) -> None:
    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    np.savez_compressed(
        path,
        **arrays,
    )


def write_spectrum_npz(
    path: Path,
    spectrum: SpectrumResult,
) -> None:
    """保存频谱 Trace 为压缩 NPZ。"""

    if (
        len(spectrum.frequencies_hz)
        != len(spectrum.amplitudes_dbm)
    ):
        raise ValueError(
            "spectrum frequency and amplitude "
            "lengths must match"
        )

    _write_arrays(
        path,
        frequency_hz=np.asarray(
            spectrum.frequencies_hz,
            dtype=np.float64,
        ),
        amplitude_dbm=np.asarray(
            spectrum.amplitudes_dbm,
            dtype=np.float64,
        ),
    )


def write_waveform_npz(
    path: Path,
    waveform: WaveformResult,
) -> None:
    """保存示波器波形为压缩 NPZ。"""

    if (
        len(waveform.time_s)
        != len(waveform.voltage_v)
    ):
        raise ValueError(
            "waveform time and voltage "
            "lengths must match"
        )

    _write_arrays(
        path,
        time_s=np.asarray(
            waveform.time_s,
            dtype=np.float64,
        ),
        voltage_v=np.asarray(
            waveform.voltage_v,
            dtype=np.float64,
        ),
    )
