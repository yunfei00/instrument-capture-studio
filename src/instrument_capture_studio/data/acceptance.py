"""Release-acceptance checks for saved capture batches."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from instrument_capture_studio.data.batch_manifest import load_batch_manifest


_REQUIRED_BY_RECIPE = {
    "ext_imm_pair": {
        "job.json",
        "metadata.json",
        "spectrum_ext.csv",
        "spectrum_ext.npz",
        "waveform_sync.csv",
        "waveform_sync.npz",
        "waveform_followup.csv",
        "waveform_followup.npz",
        "spectrum_freerun.csv",
        "spectrum_freerun.npz",
    },
    "imm_spectrum_only": {
        "job.json",
        "metadata.json",
        "spectrum_imm.csv",
        "spectrum_imm.npz",
    },
    "dsox_only": {
        "job.json",
        "metadata.json",
        "waveform_delay.csv",
        "waveform_delay.npz",
        "waveform_cycle.csv",
        "waveform_cycle.npz",
    },
}


@dataclass(frozen=True)
class BatchAcceptanceReport:
    batch_id: str
    state: str
    total_captures: int
    completed_captures: int
    successful_jobs: int
    failed_jobs: int
    recovery_events: int
    missing_files: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return (
            self.state == "succeeded"
            and self.total_captures > 0
            and self.completed_captures == self.total_captures
            and self.successful_jobs == self.completed_captures
            and not self.missing_files
        )


def validate_batch_artifacts(manifest_path: Path) -> BatchAcceptanceReport:
    """Validate each successful Job against its formal Recipe artifact set."""

    manifest_path = Path(manifest_path).expanduser().resolve()
    manifest = load_batch_manifest(manifest_path)

    jobs_value = manifest.get("jobs")
    jobs = jobs_value if isinstance(jobs_value, list) else []
    recovery_value = manifest.get("recovery_events")
    recovery_events = recovery_value if isinstance(recovery_value, list) else []

    missing: list[str] = []
    warnings: list[str] = []
    successful_jobs = 0

    for raw_job in jobs:
        if not isinstance(raw_job, dict):
            warnings.append("batch manifest contains a non-object job record")
            continue
        if str(raw_job.get("state") or "").lower() != "succeeded":
            continue

        successful_jobs += 1
        job_id = str(raw_job.get("job_id") or "").strip()
        if not job_id:
            warnings.append("successful job record is missing job_id")
            continue

        job_directory = _resolve_job_directory(
            manifest_path=manifest_path,
            job=raw_job,
            job_id=job_id,
        )
        if job_directory is None:
            missing.append(f"{job_id}: job directory not found")
            continue

        recipe = _read_recipe(job_directory)
        required = _REQUIRED_BY_RECIPE.get(recipe)
        if required is None:
            missing.append(f"{job_id}: unsupported or missing recipe {recipe!r}")
            continue

        present = {
            child.name
            for child in job_directory.iterdir()
            if child.is_file()
        }
        for filename in sorted(required - present):
            missing.append(f"{job_id}: {filename}")

    total_captures = _as_int(manifest.get("plan", {}), "total_captures")
    if total_captures <= 0:
        total_captures = _safe_int(manifest.get("total_captures"))
    completed_captures = _safe_int(manifest.get("completed_captures"))
    failed_jobs = _safe_int(manifest.get("failed_jobs"))

    if len(jobs) < successful_jobs:
        warnings.append("job count is inconsistent")
    if failed_jobs:
        warnings.append(f"batch recorded {failed_jobs} failed job attempt(s)")
    if recovery_events:
        warnings.append(
            f"batch recorded {len(recovery_events)} recovery event(s)"
        )

    return BatchAcceptanceReport(
        batch_id=str(manifest.get("batch_id") or manifest_path.parent.name),
        state=str(manifest.get("state") or "unknown").lower(),
        total_captures=total_captures,
        completed_captures=completed_captures,
        successful_jobs=successful_jobs,
        failed_jobs=failed_jobs,
        recovery_events=len(recovery_events),
        missing_files=tuple(missing),
        warnings=tuple(warnings),
    )


def _read_recipe(job_directory: Path) -> str:
    metadata_path = job_directory / "metadata.json"
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("recipe") or "").strip().lower()


def _resolve_job_directory(
    *,
    manifest_path: Path,
    job: dict[str, Any],
    job_id: str,
) -> Path | None:
    output_files = job.get("output_files")
    if isinstance(output_files, list):
        for raw_path in output_files:
            if not raw_path:
                continue
            candidate = Path(str(raw_path)).expanduser()
            if candidate.exists():
                return candidate.parent

    data_root = _data_root_from_manifest(manifest_path)
    for candidate in data_root.glob(f"*/{job_id}"):
        if candidate.is_dir():
            return candidate
    return None


def _data_root_from_manifest(manifest_path: Path) -> Path:
    try:
        return manifest_path.parents[3]
    except IndexError:
        return manifest_path.parent


def _as_int(value: object, key: str) -> int:
    if not isinstance(value, dict):
        return 0
    return _safe_int(value.get(key))


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
