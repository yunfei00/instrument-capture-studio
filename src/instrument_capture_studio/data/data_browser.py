"""Scalable summaries for browsing large capture result directories."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BatchSummary:
    manifest_path: Path
    batch_id: str
    state: str
    completed_captures: int
    total_captures: int
    failed_jobs: int
    start_hz: float | None
    stop_hz: float | None
    step_hz: float | None
    captures_per_frequency: int | None


@dataclass(frozen=True)
class JobSummary:
    manifest_path: Path
    job_id: str
    state: str

    @property
    def directory(self) -> Path:
        return self.manifest_path.parent


def _read_object(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _recent_paths(paths, limit: int) -> list[Path]:
    candidates: list[tuple[float, Path]] = []
    for path in paths:
        try:
            modified = path.stat().st_mtime
        except OSError:
            continue
        candidates.append((modified, path))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in candidates[: max(0, limit)]]


def list_recent_batches(root: Path, limit: int = 50) -> tuple[BatchSummary, ...]:
    root = Path(root)
    if not root.exists():
        return ()

    summaries: list[BatchSummary] = []
    manifests = _recent_paths(root.glob("batches/*/*/batch.json"), limit)
    for path in manifests:
        payload = _read_object(path)
        if payload is None:
            continue
        plan = payload.get("plan")
        plan = plan if isinstance(plan, dict) else {}
        summaries.append(
            BatchSummary(
                manifest_path=path,
                batch_id=str(payload.get("batch_id") or path.parent.name),
                state=str(payload.get("state") or "unknown"),
                completed_captures=int(payload.get("completed_captures") or 0),
                total_captures=int(plan.get("total_captures") or 0),
                failed_jobs=int(payload.get("failed_jobs") or 0),
                start_hz=_optional_float(plan.get("start_hz")),
                stop_hz=_optional_float(plan.get("stop_hz")),
                step_hz=_optional_float(plan.get("step_hz")),
                captures_per_frequency=_optional_int(
                    plan.get("captures_per_frequency")
                ),
            )
        )
    return tuple(summaries)


def list_recent_jobs(root: Path, limit: int = 100) -> tuple[JobSummary, ...]:
    root = Path(root)
    if not root.exists():
        return ()

    summaries: list[JobSummary] = []
    manifests = _recent_paths(root.glob("*/*/job.json"), limit)
    for path in manifests:
        payload = _read_object(path)
        if payload is None:
            continue
        summaries.append(
            JobSummary(
                manifest_path=path,
                job_id=str(payload.get("job_id") or path.parent.name),
                state=str(payload.get("state") or "unknown"),
            )
        )
    return tuple(summaries)


def _optional_float(value) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None
