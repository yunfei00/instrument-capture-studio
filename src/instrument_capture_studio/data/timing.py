"""Batch-level timing summaries derived from persisted formal Job manifests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from instrument_capture_studio.data.batch_manifest import load_batch_manifest
from instrument_capture_studio.data.job_manifest import load_job_manifest


@dataclass(frozen=True)
class TimingMetric:
    samples: int
    average_ms: float
    p95_ms: float
    max_ms: float


@dataclass(frozen=True)
class BatchTimingSummary:
    batch_id: str
    successful_jobs: int
    job_total: TimingMetric | None
    frequency_config: TimingMetric | None
    steps: dict[str, TimingMetric]


def _metric(values: list[float]) -> TimingMetric | None:
    if not values:
        return None
    ordered = sorted(values)
    count = len(ordered)
    # Linear percentile interpolation. This is deterministic for small hardware
    # acceptance runs and does not require NumPy just to summarize telemetry.
    if count == 1:
        p95 = ordered[0]
    else:
        position = (count - 1) * 0.95
        lower = int(position)
        upper = min(lower + 1, count - 1)
        fraction = position - lower
        p95 = ordered[lower] + (ordered[upper] - ordered[lower]) * fraction
    return TimingMetric(
        samples=count,
        average_ms=round(sum(ordered) / count, 3),
        p95_ms=round(p95, 3),
        max_ms=round(ordered[-1], 3),
    )


def _safe_duration(value: object) -> float | None:
    try:
        duration = float(value)
    except (TypeError, ValueError):
        return None
    if duration < 0:
        return None
    return duration


def _data_root_from_manifest(manifest_path: Path) -> Path:
    try:
        return manifest_path.parents[3]
    except IndexError:
        return manifest_path.parent


def _resolve_job_manifest(
    batch_manifest_path: Path,
    record: dict[str, object],
) -> Path | None:
    outputs = record.get("output_files")
    if isinstance(outputs, list):
        for raw in outputs:
            if not raw:
                continue
            candidate = Path(str(raw)).expanduser()
            if candidate.exists():
                job_manifest = candidate.parent / "job.json"
                if job_manifest.is_file():
                    return job_manifest

    job_id = str(record.get("job_id") or "").strip()
    if not job_id:
        return None
    root = _data_root_from_manifest(batch_manifest_path)
    for candidate in root.glob(f"*/{job_id}/job.json"):
        if candidate.is_file():
            return candidate
    return None


def summarize_batch_timings(manifest_path: Path) -> BatchTimingSummary:
    """Summarize successful formal capture timings as avg / P95 / max.

    Failed/canceled Jobs remain available in their Job manifests for diagnosis,
    but are intentionally excluded from performance aggregates so trigger
    timeouts or disconnect waits do not distort normal acquisition timing.
    """

    manifest_path = Path(manifest_path).expanduser().resolve()
    manifest = load_batch_manifest(manifest_path)
    raw_jobs = manifest.get("jobs")
    jobs = raw_jobs if isinstance(raw_jobs, list) else []

    job_values: list[float] = []
    frequency_values: list[float] = []
    step_values: dict[str, list[float]] = {}
    successful_jobs = 0

    for raw in jobs:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("state") or "").lower() != "succeeded":
            continue
        successful_jobs += 1

        frequency_duration = _safe_duration(raw.get("frequency_config_duration_ms"))
        if frequency_duration is not None:
            frequency_values.append(frequency_duration)

        job_manifest_path = _resolve_job_manifest(manifest_path, raw)
        if job_manifest_path is None:
            continue
        try:
            job_manifest = load_job_manifest(job_manifest_path)
        except (OSError, ValueError):
            continue

        job_duration = _safe_duration(job_manifest.get("duration_ms"))
        if job_duration is not None:
            job_values.append(job_duration)

        raw_steps = job_manifest.get("steps")
        if not isinstance(raw_steps, list):
            continue
        for raw_step in raw_steps:
            if not isinstance(raw_step, dict):
                continue
            if str(raw_step.get("state") or "").lower() != "succeeded":
                continue
            name = str(raw_step.get("name") or "").strip()
            duration = _safe_duration(raw_step.get("duration_ms"))
            if not name or duration is None:
                continue
            step_values.setdefault(name, []).append(duration)

    return BatchTimingSummary(
        batch_id=str(manifest.get("batch_id") or manifest_path.parent.name),
        successful_jobs=successful_jobs,
        job_total=_metric(job_values),
        frequency_config=_metric(frequency_values),
        steps={
            name: metric
            for name, values in sorted(step_values.items())
            if (metric := _metric(values)) is not None
        },
    )
