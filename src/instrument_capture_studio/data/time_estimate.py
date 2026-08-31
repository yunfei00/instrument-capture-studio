"""Historical and live-friendly duration estimates for long Batch capture."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from pathlib import Path

from instrument_capture_studio.data.data_browser import list_recent_batches
from instrument_capture_studio.data.timing import summarize_batch_timings


@dataclass(frozen=True)
class CaptureTimeEstimate:
    seconds_per_capture: float
    total_seconds: float
    samples: int
    batches: int

    def cycles(self, cycle_minutes: int) -> int:
        if cycle_minutes <= 0:
            return 0
        return max(1, ceil(self.total_seconds / (cycle_minutes * 60.0)))


def estimate_capture_time(
    root: Path,
    *,
    total_captures: int,
    batch_limit: int = 12,
) -> CaptureTimeEstimate | None:
    """Estimate one future Batch from successful persisted Job durations.

    The estimate intentionally uses full successful Job wall-clock duration,
    not FSW Sweep Time alone, so it includes both DSO-X acquisitions, EXT read,
    Free Run acquisition and result persistence. Failed/canceled Jobs are
    excluded by ``summarize_batch_timings``.
    """
    if total_captures <= 0:
        return None

    weighted_ms = 0.0
    samples = 0
    batches = 0
    for batch in list_recent_batches(Path(root), limit=batch_limit):
        try:
            summary = summarize_batch_timings(batch.manifest_path)
        except (OSError, ValueError):
            continue
        metric = summary.job_total
        if metric is None or metric.samples <= 0 or metric.average_ms <= 0:
            continue
        weighted_ms += metric.average_ms * metric.samples
        samples += metric.samples
        batches += 1

    if samples <= 0:
        return None

    seconds_per_capture = weighted_ms / samples / 1000.0
    return CaptureTimeEstimate(
        seconds_per_capture=seconds_per_capture,
        total_seconds=seconds_per_capture * total_captures,
        samples=samples,
        batches=batches,
    )
