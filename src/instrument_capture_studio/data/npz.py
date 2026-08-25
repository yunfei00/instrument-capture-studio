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


def load_spectrum_npz(
    path: Path,
    *,
    metadata: dict | None = None,
) -> SpectrumResult:
    """从 NPZ 重新加载 SpectrumResult。"""

    with np.load(
        Path(path),
        allow_pickle=False,
    ) as data:
        frequency_hz = (
            data["frequency_hz"]
            .astype(np.float64)
            .tolist()
        )

        amplitude_dbm = (
            data["amplitude_dbm"]
            .astype(np.float64)
            .tolist()
        )

    return SpectrumResult(
        frequencies_hz=frequency_hz,
        amplitudes_dbm=amplitude_dbm,
        metadata=(
            dict(metadata)
            if metadata is not None
            else {}
        ),
    )


def load_waveform_npz(
    path: Path,
    *,
    channel: str,
    sample_rate_hz: float | None = None,
    metadata: dict | None = None,
) -> WaveformResult:
    """从 NPZ 重新加载 WaveformResult。"""

    with np.load(
        Path(path),
        allow_pickle=False,
    ) as data:
        time_s = (
            data["time_s"]
            .astype(np.float64)
            .tolist()
        )

        voltage_v = (
            data["voltage_v"]
            .astype(np.float64)
            .tolist()
        )

    return WaveformResult(
        channel=channel,
        time_s=time_s,
        voltage_v=voltage_v,
        sample_rate_hz=sample_rate_hz,
        metadata=(
            dict(metadata)
            if metadata is not None
            else {}
        ),
    )
