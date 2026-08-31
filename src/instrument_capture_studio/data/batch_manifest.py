"""Persistent manifest for one frequency sweep / batch capture."""

import json
from datetime import datetime
from pathlib import Path


def build_batch_directory(
    root: Path,
    batch_id: str,
    started_at: datetime,
) -> Path:
    """Return the stable directory for one long-running Batch.

    Batch storage deliberately does not include the calendar date. A frequency
    sweep can span midnight or continue on another day, and all resumable state
    must remain under one stable directory for the lifetime of the Batch.

    ``started_at`` is retained in the signature for compatibility and remains
    recorded in ``batch.json``; it is no longer part of the filesystem path.
    """
    if not batch_id.strip():
        raise ValueError("batch_id must not be empty")
    if "/" in batch_id or "\\" in batch_id:
        raise ValueError("batch_id must not contain path separators")

    return Path(root) / "batches" / batch_id


def format_frequency_directory(
    frequency_index: int,
    frequency_hz: float,
) -> str:
    """Return a sortable, operator-readable folder name for one frequency."""
    if frequency_index < 1:
        raise ValueError("frequency_index must be at least 1")
    mhz = float(frequency_hz) / 1e6
    text = f"{mhz:.9f}".rstrip("0").rstrip(".")
    if text == "-0":
        text = "0"
    return f"f{frequency_index:03d}_{text}MHz"


def write_batch_manifest(
    path: Path,
    manifest: dict[str, object],
) -> None:
    """Write batch.json atomically so long runs keep a usable checkpoint."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


def load_batch_manifest(path: Path) -> dict[str, object]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("batch manifest must contain a JSON object")
    return value
