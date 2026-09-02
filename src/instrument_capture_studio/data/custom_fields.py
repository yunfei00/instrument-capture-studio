"""Portable editable project metadata for capture datasets.

Custom fields are deliberately stored outside NPZ payloads so project labels can
be corrected after acquisition without rewriting measurement arrays. Each sample
may carry a small ``sample_info.json`` file and Batch manifests keep the frozen
copy used when a run starts.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable

from instrument_capture_studio.data.batch_manifest import (
    format_frequency_directory,
    load_batch_manifest,
    write_batch_manifest,
)
from instrument_capture_studio.data.portable_review import scan_portable_review_samples


MAX_CUSTOM_FIELDS = 10
SAMPLE_INFO_FILENAME = "sample_info.json"


def normalize_user_fields(value: object) -> tuple[dict[str, str], ...]:
    """Validate, trim, de-duplicate and preserve at most ten name/value rows."""

    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError("项目记录必须是名称/值列表")
    if len(value) > MAX_CUSTOM_FIELDS:
        raise ValueError(f"项目记录最多 {MAX_CUSTOM_FIELDS} 项")

    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(value, start=1):
        if raw is None:
            continue
        if not isinstance(raw, dict):
            raise ValueError(f"项目记录第 {index} 项格式无效")
        name = str(raw.get("name") or "").strip()
        field_value = str(raw.get("value") or "").strip()
        if not name and not field_value:
            continue
        if not name:
            raise ValueError(f"项目记录第 {index} 项填写了值但缺少名称")
        key = name.casefold()
        if key in seen:
            raise ValueError(f"项目记录名称重复：{name}")
        seen.add(key)
        result.append({"name": name, "value": field_value})

    return tuple(result)


def read_sample_info(sample_directory: Path) -> dict[str, object]:
    path = Path(sample_directory) / SAMPLE_INFO_FILENAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_sample_user_fields(sample_directory: Path) -> tuple[dict[str, str], ...]:
    payload = read_sample_info(sample_directory)
    try:
        return normalize_user_fields(payload.get("user_fields"))
    except ValueError:
        return ()


def ensure_sample_info(
    sample_directory: Path,
    *,
    job_id: str,
    user_fields: object,
    frequency_hz: float | None = None,
) -> Path | None:
    """Create or refresh one relocatable sample_info.json when fields exist."""

    fields = normalize_user_fields(user_fields)
    if not fields:
        return None

    directory = Path(sample_directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / SAMPLE_INFO_FILENAME
    existing = read_sample_info(directory)
    existing_fields = ()
    try:
        existing_fields = normalize_user_fields(existing.get("user_fields"))
    except ValueError:
        pass

    now = _utc_now()
    if existing_fields == fields and path.is_file():
        return path

    created_at = str(existing.get("created_at") or now)
    try:
        revision = max(0, int(existing.get("revision") or 0)) + 1
    except (TypeError, ValueError):
        revision = 1

    payload: dict[str, object] = {
        "schema_version": 1,
        "job_id": str(job_id),
        "created_at": created_at,
        "updated_at": now,
        "revision": revision,
        "user_fields": list(fields),
    }
    if frequency_hz is not None:
        payload["frequency_hz"] = float(frequency_hz)
    _atomic_write_json(path, payload)
    return path


def write_sample_user_fields(
    sample_directory: Path,
    user_fields: object,
    *,
    job_id: str | None = None,
    frequency_hz: float | None = None,
) -> Path:
    """Edit one sample after acquisition without touching NPZ payloads."""

    fields = normalize_user_fields(user_fields)
    directory = Path(sample_directory).expanduser().resolve()
    if not directory.is_dir():
        raise NotADirectoryError(str(directory))
    existing = read_sample_info(directory)
    now = _utc_now()
    created_at = str(existing.get("created_at") or now)
    try:
        revision = max(0, int(existing.get("revision") or 0)) + 1
    except (TypeError, ValueError):
        revision = 1

    payload: dict[str, object] = {
        "schema_version": 1,
        "job_id": str(job_id or existing.get("job_id") or directory.name),
        "created_at": created_at,
        "updated_at": now,
        "revision": revision,
        "user_fields": list(fields),
    }
    resolved_frequency = frequency_hz if frequency_hz is not None else existing.get("frequency_hz")
    if resolved_frequency is not None:
        try:
            payload["frequency_hz"] = float(resolved_frequency)
        except (TypeError, ValueError):
            pass

    path = directory / SAMPLE_INFO_FILENAME
    _atomic_write_json(path, payload)
    return path


def update_batch_user_fields(manifest_path: Path, user_fields: object) -> int:
    """Replace Batch fields and propagate them to every existing sample folder."""

    fields = normalize_user_fields(user_fields)
    manifest_path = Path(manifest_path).expanduser().resolve()
    manifest = load_batch_manifest(manifest_path)
    manifest["user_fields"] = list(fields)
    manifest["user_fields_updated_at"] = _utc_now()
    write_batch_manifest(manifest_path, manifest)

    updated = 0
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        return updated
    for raw in jobs:
        if not isinstance(raw, dict):
            continue
        job_id = str(raw.get("job_id") or "").strip()
        if not job_id:
            continue
        try:
            frequency_index = int(raw.get("frequency_index"))
            frequency_hz = float(raw.get("frequency_hz"))
        except (TypeError, ValueError):
            continue
        directory = (
            manifest_path.parent
            / format_frequency_directory(frequency_index, frequency_hz)
            / job_id
        )
        if not directory.is_dir():
            continue
        write_sample_user_fields(
            directory,
            fields,
            job_id=job_id,
            frequency_hz=frequency_hz,
        )
        updated += 1
    return updated


def update_directory_user_fields(root: Path, user_fields: object) -> int:
    """Apply fields to all portable complete paired samples below any data root."""

    fields = normalize_user_fields(user_fields)
    scan = scan_portable_review_samples(root)
    for sample in scan.samples:
        write_sample_user_fields(
            sample.directory,
            fields,
            job_id=sample.directory.name,
            frequency_hz=sample.frequency_hz,
        )
    return len(scan.samples)


def fields_from_mapping(items: Iterable[tuple[str, str]]) -> tuple[dict[str, str], ...]:
    return normalize_user_fields(
        [{"name": name, "value": value} for name, value in items]
    )


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
