import json
from datetime import datetime
from pathlib import Path
from typing import Any

from instrument_capture_studio.core.results import SpectrumResult
from instrument_capture_studio.workflows.context import CaptureContext


def _spectrum_summary(spectrum: SpectrumResult | None) -> dict[str, Any] | None:
    if spectrum is None:
        return None
    return {
        "points": spectrum.points,
        "start_frequency_hz": (
            spectrum.frequencies_hz[0] if spectrum.points else None
        ),
        "stop_frequency_hz": (
            spectrum.frequencies_hz[-1] if spectrum.points else None
        ),
        "metadata": spectrum.metadata,
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
    """把 CaptureContext 转换为可持久化的 Job 元数据。

    Schema v1 remains unchanged for legacy single-spectrum jobs. Schema v2 is
    selected automatically when a paired EXT/IMM spectrum is present.
    """

    timestamp = captured_at or datetime.now()
    waveform = context.waveform

    metadata: dict[str, Any] = {
        "schema_version": context.schema_version,
        "job_id": job_id,
        "captured_at": timestamp.isoformat(),
        "capture_complete": context.capture_complete,
        "measurements": {
            "delay": _measurement_summary(context.delay),
            "cycle_count": _measurement_summary(context.cycle_count),
        },
        "waveform": (
            None
            if waveform is None
            else {
                "channel": waveform.channel,
                "points": waveform.points,
                "sample_rate_hz": waveform.sample_rate_hz,
                "metadata": waveform.metadata,
            }
        ),
        "metadata": context.metadata,
    }

    if context.schema_version == 1:
        metadata["spectrum"] = _spectrum_summary(context.spectrum)
    else:
        metadata["spectra"] = {
            "ext": _spectrum_summary(context.spectrum_ext),
            "imm": _spectrum_summary(context.spectrum_imm),
        }
        # Explicit recipe marker makes downstream dataset tooling unambiguous.
        metadata["recipe"] = str(
            context.metadata.get("recipe", "ext_imm_pair")
        )

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
