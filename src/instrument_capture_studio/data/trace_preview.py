"""Load saved NPZ traces into a lightweight preview model."""

import json
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
    details: tuple[str, ...] = ()


def _trace_title(path: Path, kind: str) -> str:
    stem = path.stem.lower()
    if kind == "spectrum":
        if stem == "spectrum_ext":
            return "Spectrum EXT"
        if stem == "spectrum_freerun":
            return "Spectrum Free Run"
        if stem == "spectrum_imm":
            return "Spectrum IMM"
        return "Spectrum"

    if stem == "waveform_sync":
        return "Waveform Sync"
    if stem == "waveform_followup":
        return "Waveform Follow-up"
    if stem == "waveform_delay":
        return "Waveform DELAY"
    if stem == "waveform_cycle":
        return "Waveform CYCLE_COUNT"
    return "Waveform"


def load_trace_preview(path: Path, max_points: int = 5000) -> TracePreview:
    path = Path(path)
    if max_points < 2:
        raise ValueError("max_points must be at least 2")

    with np.load(path, allow_pickle=False) as archive:
        keys = set(archive.files)
        if {"time_s", "amplitude_dbm"} <= keys:
            raw_time = np.asarray(archive["time_s"], dtype=np.float64)
            x, x_label = _scaled_spectrum_time_axis(raw_time)
            y = np.asarray(archive["amplitude_dbm"], dtype=np.float64)
            title = _trace_title(path, "spectrum")
            y_label = "Amplitude (dBm)"
            details = _zero_span_details(archive, raw_time)
        elif {"frequency_hz", "amplitude_dbm"} <= keys:
            frequency_hz = np.asarray(archive["frequency_hz"], dtype=np.float64)
            y = np.asarray(archive["amplitude_dbm"], dtype=np.float64)
            legacy_axis = _legacy_zero_span_axis(path, frequency_hz)
            if legacy_axis is not None:
                x, x_label, details = legacy_axis
            else:
                x = frequency_hz / 1e6
                x_label = "Frequency (MHz)"
                details = ()
            title = _trace_title(path, "spectrum")
            y_label = "Amplitude (dBm)"
        elif {"time_s", "voltage_v"} <= keys:
            x = np.asarray(archive["time_s"], dtype=np.float64) * 1e6
            y = np.asarray(archive["voltage_v"], dtype=np.float64)
            title = _trace_title(path, "waveform")
            x_label = "Time (µs)"
            y_label = "Voltage (V)"
            details = ()
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
        details=details,
    )


def _scaled_spectrum_time_axis(time_s: np.ndarray) -> tuple[np.ndarray, str]:
    maximum = float(np.max(np.abs(time_s))) if time_s.size else 0.0
    if maximum <= 1e-3:
        return time_s * 1e6, "Time (µs)"
    if maximum <= 1.0:
        return time_s * 1e3, "Time (ms)"
    return time_s, "Time (s)"


def _zero_span_details(archive, time_s: np.ndarray) -> tuple[str, ...]:
    details = ["Zero Span · time-domain power trace"]
    if "center_frequency_hz" in archive.files:
        center_hz = float(np.asarray(archive["center_frequency_hz"]).item())
        details.append(f"Center {center_hz / 1e6:g} MHz")
    if "sweep_time_s" in archive.files:
        sweep_time_s = float(np.asarray(archive["sweep_time_s"]).item())
    elif time_s.size:
        sweep_time_s = float(time_s[-1] - time_s[0])
    else:
        sweep_time_s = 0.0
    if sweep_time_s > 0:
        details.append(f"Sweep Time {sweep_time_s:g} s")
    return tuple(details)


def _legacy_zero_span_axis(
    path: Path,
    frequency_hz: np.ndarray,
) -> tuple[np.ndarray, str, tuple[str, ...]] | None:
    """Repair v1.0.0 Zero Span NPZ files whose frequency axis is constant."""
    if frequency_hz.size < 2:
        return None
    center_hz = float(frequency_hz[0])
    if not np.allclose(frequency_hz, center_hz, rtol=0.0, atol=max(1e-6, abs(center_hz) * 1e-12)):
        return None

    sweep_time_s = _read_legacy_sweep_time(path.parent / "metadata.json")
    if sweep_time_s is not None and sweep_time_s > 0:
        raw_time = np.linspace(0.0, sweep_time_s, frequency_hz.size, dtype=np.float64)
        x, label = _scaled_spectrum_time_axis(raw_time)
        return (
            x,
            label,
            (
                "Legacy Zero Span · reconstructed from metadata",
                f"Center {center_hz / 1e6:g} MHz",
                f"Sweep Time {sweep_time_s:g} s",
            ),
        )

    # Old standalone Zero Span files may not contain Sweep Time. Do not draw a
    # misleading vertical frequency line; preserve the trace shape on point index
    # and state explicitly that the exact time base cannot be recovered.
    return (
        np.arange(frequency_hz.size, dtype=np.float64),
        "Trace point",
        (
            "Legacy Zero Span · Sweep Time unavailable",
            f"Center {center_hz / 1e6:g} MHz",
        ),
    )


def _read_legacy_sweep_time(metadata_path: Path) -> float | None:
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _find_positive_number(payload, ("sweep_time_s", "fsw_sweep_time_s"))


def _find_positive_number(value, keys: tuple[str, ...]) -> float | None:
    if isinstance(value, dict):
        for key in keys:
            raw = value.get(key)
            try:
                number = float(raw)
            except (TypeError, ValueError):
                pass
            else:
                if number > 0:
                    return number
        for child in value.values():
            result = _find_positive_number(child, keys)
            if result is not None:
                return result
    elif isinstance(value, list):
        for child in value:
            result = _find_positive_number(child, keys)
            if result is not None:
                return result
    return None
