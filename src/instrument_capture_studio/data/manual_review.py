"""Manual post-acquisition screening for complete paired capture samples."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil

from instrument_capture_studio.data.batch_manifest import (
    format_frequency_directory,
    load_batch_manifest,
    write_batch_manifest,
)


FORMAL_REVIEW_TRACES = (
    "spectrum_ext.npz",
    "waveform_sync.npz",
    "waveform_followup.npz",
    "spectrum_freerun.npz",
)


@dataclass(frozen=True)
class ReviewSample:
    """One successful logical sample eligible for human screening."""

    job_id: str
    frequency_hz: float
    frequency_index: int
    capture_index: int
    directory: Path

    @property
    def trace_paths(self) -> tuple[Path, ...]:
        return tuple(self.directory / name for name in FORMAL_REVIEW_TRACES)


@dataclass(frozen=True)
class ReviewDeleteResult:
    job_id: str
    directory: Path
    rejected_count: int


def list_review_samples(
    manifest_path: Path,
    *,
    frequency_index: int | None = None,
) -> tuple[ReviewSample, ...]:
    """Return successful, non-rejected Batch samples in acquisition order."""

    manifest_path = Path(manifest_path).expanduser().resolve()
    manifest = load_batch_manifest(manifest_path)
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        return ()

    samples: list[ReviewSample] = []
    for raw in jobs:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("state") or "").lower() != "succeeded":
            continue
        if str(raw.get("review_status") or "").lower() == "rejected":
            continue
        try:
            item_frequency_index = int(raw.get("frequency_index"))
            frequency_hz = float(raw.get("frequency_hz"))
            capture_index = int(raw.get("capture_index"))
        except (TypeError, ValueError):
            continue
        if frequency_index is not None and item_frequency_index != frequency_index:
            continue

        job_id = str(raw.get("job_id") or "").strip()
        if not job_id:
            continue
        directory = _expected_job_directory(
            manifest_path,
            job_id=job_id,
            frequency_index=item_frequency_index,
            frequency_hz=frequency_hz,
        )
        if not directory.is_dir():
            continue
        samples.append(
            ReviewSample(
                job_id=job_id,
                frequency_hz=frequency_hz,
                frequency_index=item_frequency_index,
                capture_index=capture_index,
                directory=directory,
            )
        )

    samples.sort(
        key=lambda sample: (
            sample.frequency_index,
            sample.capture_index,
            sample.job_id,
        )
    )
    return tuple(samples)


def reject_review_sample(
    manifest_path: Path,
    job_id: str,
) -> ReviewDeleteResult:
    """Reject one sample, delete its entire Job directory, and keep audit state.

    There is intentionally no confirmation layer here; the full-screen review UI
    maps Delete directly to this operation. Safety comes from strict Batch/frequency
    path validation and an atomic directory rename before the manifest is updated.
    """

    manifest_path = Path(manifest_path).expanduser().resolve()
    manifest = load_batch_manifest(manifest_path)
    batch_state = str(manifest.get("state") or "unknown").lower()
    if batch_state in {"running", "paused"}:
        raise RuntimeError("正在运行或暂停待继续的 Batch 不允许人工删除样本")

    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("batch manifest does not contain jobs")

    matches = [
        raw
        for raw in jobs
        if isinstance(raw, dict) and str(raw.get("job_id") or "") == job_id
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one Job record for {job_id!r}")
    record = matches[0]
    if str(record.get("review_status") or "").lower() == "rejected":
        raise ValueError(f"Job is already rejected: {job_id}")

    try:
        frequency_index = int(record.get("frequency_index"))
        frequency_hz = float(record.get("frequency_hz"))
    except (TypeError, ValueError):
        raise ValueError("Job record is missing a valid frequency") from None

    job_directory = _expected_job_directory(
        manifest_path,
        job_id=job_id,
        frequency_index=frequency_index,
        frequency_hz=frequency_hz,
    )
    _validate_delete_target(
        manifest_path,
        job_directory,
        job_id=job_id,
        frequency_index=frequency_index,
        frequency_hz=frequency_hz,
    )
    if not job_directory.is_dir():
        raise FileNotFoundError(str(job_directory))

    tombstone = job_directory.with_name(f".{job_directory.name}.review-delete")
    if tombstone.exists():
        raise RuntimeError(f"review delete staging path already exists: {tombstone}")

    # Rename is atomic on the same filesystem. If the manifest update fails we
    # restore the directory, so a failed review operation cannot silently lose data.
    job_directory.rename(tombstone)
    now = datetime.now(timezone.utc).isoformat()
    original_outputs = list(record.get("output_files") or [])
    try:
        record["review_status"] = "rejected"
        record["reviewed_at"] = now
        record["deleted_at"] = now
        record["review_reason"] = "manual_screening"
        record["review_deleted_output_files"] = original_outputs
        record["output_files"] = []
        manifest["review_summary"] = _build_review_summary(jobs, now)
        write_batch_manifest(manifest_path, manifest)
    except Exception:
        tombstone.rename(job_directory)
        raise

    shutil.rmtree(tombstone)
    summary = manifest.get("review_summary")
    rejected_count = (
        int(summary.get("rejected_count") or 0)
        if isinstance(summary, dict)
        else 0
    )
    return ReviewDeleteResult(
        job_id=job_id,
        directory=job_directory,
        rejected_count=rejected_count,
    )


def _expected_job_directory(
    manifest_path: Path,
    *,
    job_id: str,
    frequency_index: int,
    frequency_hz: float,
) -> Path:
    return (
        manifest_path.parent
        / format_frequency_directory(frequency_index, frequency_hz)
        / job_id
    )


def _validate_delete_target(
    manifest_path: Path,
    job_directory: Path,
    *,
    job_id: str,
    frequency_index: int,
    frequency_hz: float,
) -> None:
    batch_directory = manifest_path.parent.resolve()
    expected_frequency = (
        batch_directory / format_frequency_directory(frequency_index, frequency_hz)
    ).resolve()
    target = job_directory.resolve()

    if target.name != job_id:
        raise ValueError("refusing to delete: Job directory name mismatch")
    if target.parent != expected_frequency:
        raise ValueError("refusing to delete: Job is outside the expected frequency directory")
    if batch_directory not in target.parents:
        raise ValueError("refusing to delete: Job is outside the selected Batch")
    if target in {batch_directory, expected_frequency}:
        raise ValueError("refusing to delete a Batch or frequency root")


def _build_review_summary(jobs: list[object], reviewed_at: str) -> dict[str, object]:
    rejected = 0
    succeeded = 0
    for raw in jobs:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("state") or "").lower() == "succeeded":
            succeeded += 1
        if str(raw.get("review_status") or "").lower() == "rejected":
            rejected += 1
    return {
        "rejected_count": rejected,
        "remaining_successful_samples": max(0, succeeded - rejected),
        "last_reviewed_at": reviewed_at,
    }
