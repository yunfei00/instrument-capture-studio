"""Load saved NPZ traces into a lightweight preview model."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class TracePreview:
    title: str
    x: np.ndarray
    y: np.ndarray
    x_label: str
    y_label: str


def load_trace_preview(path: Path, max_points: int = 5000) -> TracePreview:
    path = Path(path)
    if max_points < 2:
        raise ValueError("max_points must be at least 2")

    with np.load(path, allow_pickle=False) as archive:
        keys = set(archive.files)
        if {"frequency_hz", "amplitude_dbm"} <= keys:
            x = np.asarray(archive["frequency_hz"], dtype=np.float64) / 1e6
            y = np.asarray(archive["amplitude_dbm"], dtype=np.float64)
            title = "Spectrum"
            x_label = "Frequency (MHz)"
            y_label = "Amplitude (dBm)"
        elif {"time_s", "voltage_v"} <= keys:
            x = np.asarray(archive["time_s"], dtype=np.float64) * 1e6
            y = np.asarray(archive["voltage_v"], dtype=np.float64)
            title = "Waveform"
            x_label = "Time (µs)"
            y_label = "Voltage (V)"
        else:
            raise ValueError(f"unsupported trace NPZ keys: {sorted(keys)}")

    if x.ndim != 1 or y.ndim != 1:
        raise ValueError("trace arrays must be one-dimensional")
    if x.size != y.size:
        raise ValueError("trace x/y arrays must have equal length")
    if x.size == 0:
        raise ValueError("trace arrays must not be empty")

    if x.size > max_points:
        indices = np.linspace(0, x.size - 1, max_points, dtype=np.int64)
        x = x[indices]
        y = y[indices]

    return TracePreview(
        title=title,
        x=x,
        y=y,
        x_label=x_label,
        y_label=y_label,
    )
