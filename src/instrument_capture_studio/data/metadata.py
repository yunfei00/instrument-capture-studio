import json
from datetime import datetime
from pathlib import Path
from typing import Any

from instrument_capture_studio.workflows.context import (
    CaptureContext,
)


def build_capture_metadata(
    job_id: str,
    context: CaptureContext,
    *,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    """把 CaptureContext 转换为可持久化的 Job 元数据。"""

    timestamp = (
        captured_at
        or datetime.now()
    )

    spectrum = context.spectrum
    delay = context.delay
    cycle_count = context.cycle_count
    waveform = context.waveform

    return {
        "schema_version": 1,
        "job_id": job_id,
        "captured_at": timestamp.isoformat(),
        "capture_complete": context.is_complete,
        "measurements": {
            "delay": (
                None
                if delay is None
                else {
                    "measurement": delay.measurement,
                    "value": delay.value,
                    "unit": delay.unit,
                    "metadata": delay.metadata,
                }
            ),
            "cycle_count": (
                None
                if cycle_count is None
                else {
                    "measurement": cycle_count.measurement,
                    "value": cycle_count.value,
                    "unit": cycle_count.unit,
                    "metadata": cycle_count.metadata,
                }
            ),
        },
        "spectrum": (
            None
            if spectrum is None
            else {
                "points": spectrum.points,
                "start_frequency_hz": (
                    spectrum.frequencies_hz[0]
                    if spectrum.points
                    else None
                ),
                "stop_frequency_hz": (
                    spectrum.frequencies_hz[-1]
                    if spectrum.points
                    else None
                ),
                "metadata": spectrum.metadata,
            }
        ),
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


def write_capture_metadata(
    path: Path,
    metadata: dict[str, Any],
) -> None:
    """将 Job 元数据写入 UTF-8 JSON 文件。"""

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metadata,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")


def load_capture_metadata(
    path: Path,
) -> dict[str, Any]:
    """重新加载 metadata.json。"""

    with Path(path).open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)
