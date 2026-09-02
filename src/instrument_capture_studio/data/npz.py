import json
from pathlib import Path

import numpy as np

from instrument_capture_studio.core.results import SpectrumResult, WaveformResult


def _write_arrays(path: Path, **arrays) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)


def write_spectrum_npz(path: Path, spectrum: SpectrumResult) -> None:
    """保存频谱 Trace 为压缩 NPZ。

    Zero Span 同时保存 ``time_s`` 与兼容用 ``frequency_hz``。预览和报告
    优先使用时间轴，中心频率仍保留用于测量条件和旧调用方兼容。
    """

    if len(spectrum.frequencies_hz) != len(spectrum.amplitudes_dbm):
        raise ValueError("spectrum frequency and amplitude lengths must match")

    arrays = {
        "frequency_hz": np.asarray(spectrum.frequencies_hz, dtype=np.float64),
        "amplitude_dbm": np.asarray(spectrum.amplitudes_dbm, dtype=np.float64),
    }

    if spectrum.time_s is not None:
        if len(spectrum.time_s) != len(spectrum.amplitudes_dbm):
            raise ValueError("spectrum time and amplitude lengths must match")
        arrays["time_s"] = np.asarray(spectrum.time_s, dtype=np.float64)
        for key in ("center_frequency_hz", "span_hz", "sweep_time_s"):
            value = spectrum.metadata.get(key)
            if value is not None:
                arrays[key] = np.asarray(float(value), dtype=np.float64)

    _write_arrays(path, **arrays)


def write_waveform_npz(path: Path, waveform: WaveformResult) -> None:
    """保存示波器波形及可移植元数据为压缩 NPZ。

    ``metadata_json`` keeps optional Snapshot All values attached to the waveform
    when NPZ files are copied away from Batch/job metadata. Older readers ignore
    this extra array, while the current loader restores it automatically.
    """

    if len(waveform.time_s) != len(waveform.voltage_v):
        raise ValueError("waveform time and voltage lengths must match")

    arrays = {
        "time_s": np.asarray(waveform.time_s, dtype=np.float64),
        "voltage_v": np.asarray(waveform.voltage_v, dtype=np.float64),
    }
    if waveform.metadata:
        arrays["metadata_json"] = np.asarray(
            json.dumps(
                waveform.metadata,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
        )
    _write_arrays(path, **arrays)


def load_spectrum_npz(
    path: Path,
    *,
    metadata: dict | None = None,
) -> SpectrumResult:
    """从 NPZ 重新加载 SpectrumResult。"""

    with np.load(Path(path), allow_pickle=False) as data:
        frequency_hz = data["frequency_hz"].astype(np.float64).tolist()
        amplitude_dbm = data["amplitude_dbm"].astype(np.float64).tolist()
        time_s = (
            data["time_s"].astype(np.float64).tolist()
            if "time_s" in data.files
            else None
        )
        loaded_metadata = dict(metadata) if metadata is not None else {}
        for key in ("center_frequency_hz", "span_hz", "sweep_time_s"):
            if key in data.files:
                loaded_metadata.setdefault(key, float(np.asarray(data[key]).item()))
        if time_s is not None:
            loaded_metadata.setdefault("axis_kind", "time")
            loaded_metadata.setdefault("zero_span", True)

    return SpectrumResult(
        frequencies_hz=frequency_hz,
        amplitudes_dbm=amplitude_dbm,
        metadata=loaded_metadata,
        time_s=time_s,
    )


def load_waveform_npz(
    path: Path,
    *,
    channel: str,
    sample_rate_hz: float | None = None,
    metadata: dict | None = None,
) -> WaveformResult:
    """从 NPZ 重新加载 WaveformResult，包括内嵌 Snapshot All 元数据。"""

    with np.load(Path(path), allow_pickle=False) as data:
        time_s = data["time_s"].astype(np.float64).tolist()
        voltage_v = data["voltage_v"].astype(np.float64).tolist()
        loaded_metadata: dict = {}
        if "metadata_json" in data.files:
            try:
                embedded = json.loads(str(np.asarray(data["metadata_json"]).item()))
            except (TypeError, ValueError, json.JSONDecodeError):
                embedded = {}
            if isinstance(embedded, dict):
                loaded_metadata.update(embedded)

    if metadata is not None:
        loaded_metadata.update(dict(metadata))

    return WaveformResult(
        channel=channel,
        time_s=time_s,
        voltage_v=voltage_v,
        sample_rate_hz=sample_rate_hz,
        metadata=loaded_metadata,
    )
