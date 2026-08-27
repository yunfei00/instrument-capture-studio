import json
from datetime import datetime
from pathlib import Path
from typing import Any

from instrument_capture_studio.core.results import SpectrumResult, WaveformResult
from instrument_capture_studio.workflows.context import CaptureContext


def _spectrum_summary(spectrum: SpectrumResult | None) -> dict[str, Any] | None:
    if spectrum is None:
        return None
    return {
        "points": spectrum.points,
        "start_frequency_hz": spectrum.frequencies_hz[0] if spectrum.points else None,
        "stop_frequency_hz": spectrum.frequencies_hz[-1] if spectrum.points else None,
        "metadata": spectrum.metadata,
    }


def _waveform_summary(waveform: WaveformResult | None) -> dict[str, Any] | None:
    if waveform is None:
        return None
    return {
        "channel": waveform.channel,
        "points": waveform.points,
        "sample_rate_hz": waveform.sample_rate_hz,
        "metadata": waveform.metadata,
    }


def _measurement_summary(value):
    if value is None:
        return None
    return {
        "measurement": value.measurement,
        "value": value.value,
        "unit": value.unit,
        "metadata": value.metadata,
    }


def build_capture_metadata(
    job_id: str,
    context: CaptureContext,
    *,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    """把 CaptureContext 转换为正式 schema-v1 Job 元数据。

    调试数据无需向后兼容，因此正式格式从 schema v1 重新开始。Recipe 明确
    决定一个 Job 应包含哪些物理采集；EXT 配对样本有两份频谱和两次独立
    示波器采集。
    """

    timestamp = captured_at or datetime.now()
    recipe = str(context.metadata.get("recipe") or "legacy_debug")

    metadata: dict[str, Any] = {
        "schema_version": 1,
        "job_id": job_id,
        "captured_at": timestamp.isoformat(),
        "recipe": recipe,
        "capture_complete": context.capture_complete,
        "spectra": {
            "ext": _spectrum_summary(context.spectrum_ext),
            "imm": _spectrum_summary(context.spectrum_imm),
        },
        "oscilloscope": {
            "waveform_channel": context.metadata.get("waveform_channel"),
            "delay": {
                "measurement": _measurement_summary(context.delay),
                "waveform": _waveform_summary(context.waveform_delay),
            },
            "cycle_count": {
                "measurement": _measurement_summary(context.cycle_count),
                "waveform": _waveform_summary(context.waveform_cycle),
            },
        },
        "metadata": context.metadata,
    }

    # Temporary internal debug workflows still use generic fields. Keep them
    # only so the existing regression suite can exercise old plumbing; formal
    # Recipe data never relies on these names and no historical files need to
    # remain readable.
    if context.spectrum is not None:
        metadata["debug_spectrum"] = _spectrum_summary(context.spectrum)
    if context.waveform is not None:
        metadata["debug_waveform"] = _waveform_summary(context.waveform)
    if context.delay is not None and context.waveform_delay is None:
        metadata["debug_delay"] = _measurement_summary(context.delay)
    if context.cycle_count is not None and context.waveform_cycle is None:
        metadata["debug_cycle_count"] = _measurement_summary(context.cycle_count)

    return metadata


def write_capture_metadata(path: Path, metadata: dict[str, Any]) -> None:
    """将 Job 元数据写入 UTF-8 JSON 文件。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
        file.write("\n")


def load_capture_metadata(path: Path) -> dict[str, Any]:
    """重新加载 metadata.json。"""
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)
