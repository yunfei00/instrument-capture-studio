"""Scalable summaries for browsing large capture result directories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from instrument_capture_studio.data.batch_manifest import format_frequency_directory


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


@dataclass(frozen=True)
class BatchJobSummary:
    """One recorded Job from batch.json without eagerly opening job.json."""

    job_id: str
    state: str
    frequency_hz: float
    frequency_index: int
    capture_index: int
    attempt: int
    started_at: str | None
    finished_at: str | None
    directory: Path
    output_files: tuple[Path, ...]


@dataclass(frozen=True)
class BatchFrequencySummary:
    """All Job records belonging to one planned frequency."""

    frequency_index: int
    frequency_hz: float
    directory: Path
    jobs: tuple[BatchJobSummary, ...]

    @property
    def succeeded_jobs(self) -> int:
        return sum(1 for job in self.jobs if job.state.lower() == "succeeded")

    @property
    def failed_jobs(self) -> int:
        return sum(1 for job in self.jobs if job.state.lower() != "succeeded")


def _read_object(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _recent_paths(paths, limit: int) -> list[Path]:
    candidates: list[tuple[float, Path]] = []
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        try:
            modified = path.stat().st_mtime
        except OSError:
            continue
        candidates.append((modified, path))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in candidates[: max(0, limit)]]


def _batch_manifest_paths(root: Path):
    # v1.0.1+: <root>/batches/<batch-id>/batch.json
    yield from root.glob("batches/*/batch.json")
    # v1.0.0 compatibility: <root>/batches/YYYY-MM-DD/<batch-id>/batch.json
    yield from root.glob("batches/*/*/batch.json")


def list_recent_batches(root: Path, limit: int = 50) -> tuple[BatchSummary, ...]:
    root = Path(root)
    if not root.exists():
        return ()

    summaries: list[BatchSummary] = []
    manifests = _recent_paths(_batch_manifest_paths(root), limit)
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


def list_batch_frequency_groups(
    manifest_path: Path,
) -> tuple[BatchFrequencySummary, ...]:
    """Read one batch.json and group every recorded Job by frequency.

    The data page uses this index instead of recursively scanning thousands of
    Job folders. Planned frequencies with no completed Job are included so a
    running Batch still shows its full acquisition plan.
    """

    manifest_path = Path(manifest_path)
    payload = _read_object(manifest_path)
    if payload is None:
        return ()

    plan = payload.get("plan")
    plan = plan if isinstance(plan, dict) else {}
    raw_frequencies = plan.get("frequencies_hz")
    frequencies: list[float] = []
    if isinstance(raw_frequencies, list):
        for value in raw_frequencies:
            parsed = _optional_float(value)
            if parsed is not None:
                frequencies.append(parsed)

    if not frequencies:
        start = _optional_float(plan.get("start_hz"))
        stop = _optional_float(plan.get("stop_hz"))
        step = _optional_float(plan.get("step_hz"))
        if start is not None and stop is not None and step is not None and step > 0:
            value = start
            tolerance = max(1e-9, abs(step) * 1e-9)
            while value <= stop + tolerance:
                frequencies.append(value)
                value += step

    jobs_by_index: dict[int, list[BatchJobSummary]] = {
        index: [] for index in range(1, len(frequencies) + 1)
    }
    raw_jobs = payload.get("jobs")
    if isinstance(raw_jobs, list):
        for raw in raw_jobs:
            if not isinstance(raw, dict):
                continue
            frequency_index = _optional_int(raw.get("frequency_index"))
            frequency_hz = _optional_float(raw.get("frequency_hz"))
            if frequency_index is None or frequency_index < 1 or frequency_hz is None:
                continue
            if frequency_index > len(frequencies):
                frequencies.extend(
                    [frequency_hz] * (frequency_index - len(frequencies))
                )
                for index in range(1, len(frequencies) + 1):
                    jobs_by_index.setdefault(index, [])

            output_files = _output_paths(raw.get("output_files"))
            directory = _job_directory(
                manifest_path,
                raw,
                frequency_index=frequency_index,
                frequency_hz=frequency_hz,
                output_files=output_files,
            )
            jobs_by_index.setdefault(frequency_index, []).append(
                BatchJobSummary(
                    job_id=str(raw.get("job_id") or directory.name),
                    state=str(raw.get("state") or "unknown"),
                    frequency_hz=frequency_hz,
                    frequency_index=frequency_index,
                    capture_index=_optional_int(raw.get("capture_index")) or 0,
                    attempt=_optional_int(raw.get("attempt")) or 1,
                    started_at=_optional_text(raw.get("started_at")),
                    finished_at=_optional_text(raw.get("finished_at")),
                    directory=directory,
                    output_files=output_files,
                )
            )

    groups: list[BatchFrequencySummary] = []
    for index, frequency_hz in enumerate(frequencies, start=1):
        jobs = jobs_by_index.get(index, [])
        jobs.sort(key=lambda job: (job.capture_index, job.attempt, job.job_id))
        groups.append(
            BatchFrequencySummary(
                frequency_index=index,
                frequency_hz=frequency_hz,
                directory=manifest_path.parent
                / format_frequency_directory(index, frequency_hz),
                jobs=tuple(jobs),
            )
        )
    return tuple(groups)


def list_recent_jobs(root: Path, limit: int = 100) -> tuple[JobSummary, ...]:
    """Return recent Jobs without recursively scanning every Batch directory.

    Standalone v1 jobs are discovered from their shallow date layout. Batch
    jobs come from batch.json, which scales much better than rglob("job.json")
    once one frequency contains hundreds or thousands of samples.
    """

    root = Path(root)
    if not root.exists():
        return ()

    candidates: dict[Path, tuple[float, JobSummary]] = {}

    # Standalone/legacy jobs: <root>/<date>/<job>/job.json.
    for path in root.glob("*/*/job.json"):
        if "batches" in path.parts:
            continue
        payload = _read_object(path)
        if payload is None:
            continue
        try:
            modified = path.stat().st_mtime
        except OSError:
            continue
        summary = JobSummary(
            manifest_path=path,
            job_id=str(payload.get("job_id") or path.parent.name),
            state=str(payload.get("state") or "unknown"),
        )
        candidates[path] = (modified, summary)

    # Batch jobs: index records from the much smaller set of batch manifests.
    for batch_path in _batch_manifest_paths(root):
        groups = list_batch_frequency_groups(batch_path)
        try:
            batch_modified = batch_path.stat().st_mtime
        except OSError:
            batch_modified = 0.0
        for group in groups:
            for job in group.jobs:
                job_manifest = job.directory / "job.json"
                timestamp = _timestamp(job.finished_at or job.started_at)
                if timestamp is None:
                    try:
                        timestamp = job_manifest.stat().st_mtime
                    except OSError:
                        timestamp = batch_modified
                summary = JobSummary(
                    manifest_path=job_manifest,
                    job_id=job.job_id,
                    state=job.state,
                )
                previous = candidates.get(job_manifest)
                if previous is None or timestamp > previous[0]:
                    candidates[job_manifest] = (timestamp, summary)

    ordered = sorted(candidates.values(), key=lambda item: item[0], reverse=True)
    return tuple(summary for _, summary in ordered[: max(0, limit)])


def _output_paths(value: object) -> tuple[Path, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(Path(str(item)) for item in value if str(item).strip())


def _job_directory(
    manifest_path: Path,
    raw: dict[str, object],
    *,
    frequency_index: int,
    frequency_hz: float,
    output_files: tuple[Path, ...],
) -> Path:
    for path in output_files:
        if path.exists():
            return path.parent

    job_id = str(raw.get("job_id") or "").strip()
    candidate = (
        manifest_path.parent
        / format_frequency_directory(frequency_index, frequency_hz)
        / job_id
    )
    if candidate.exists() or not output_files:
        return candidate

    # When a dataset has been moved to another machine, stored absolute output
    # paths may be stale. Prefer the current Batch-relative v1.0.1 location.
    return candidate


def _timestamp(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except (ValueError, OSError, OverflowError):
        return None


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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
