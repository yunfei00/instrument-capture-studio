import json
from datetime import datetime
from pathlib import Path
from typing import Any

from instrument_capture_studio.core.models import (
    CaptureResult,
)


def _datetime_text(
    value: datetime | None,
) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def _duration_ms(
    started_at: datetime | None,
    finished_at: datetime | None,
) -> float | None:
    if started_at is None or finished_at is None:
        return None
    return round(
        max(0.0, (finished_at - started_at).total_seconds() * 1000.0),
        3,
    )


def build_job_manifest(
    result: CaptureResult,
) -> dict[str, Any]:
    """把 CaptureResult 转为可持久化 Job 清单，并记录节点耗时。"""

    return {
        "schema_version": 1,
        "job_id": result.job_id,
        "state": result.state.value,
        "started_at": _datetime_text(
            result.started_at
        ),
        "finished_at": _datetime_text(
            result.finished_at
        ),
        "duration_ms": _duration_ms(
            result.started_at,
            result.finished_at,
        ),
        "steps": [
            {
                "name": step.name,
                "state": step.state.value,
                "started_at": _datetime_text(
                    step.started_at
                ),
                "finished_at": _datetime_text(
                    step.finished_at
                ),
                "duration_ms": _duration_ms(
                    step.started_at,
                    step.finished_at,
                ),
                "error": step.error,
                "metadata": dict(
                    step.metadata
                ),
            }
            for step in result.steps
        ],
        "output_files": list(
            result.output_files
        ),
        "metadata": dict(
            result.metadata
        ),
    }


def write_job_manifest(
    path: Path,
    manifest: dict[str, Any],
) -> None:
    """保存 job.json。"""

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
            manifest,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")


def load_job_manifest(
    path: Path,
) -> dict[str, Any]:
    """重新加载 job.json。"""

    with Path(path).open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)
