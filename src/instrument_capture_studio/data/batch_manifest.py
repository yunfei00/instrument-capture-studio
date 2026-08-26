"""Persistent manifest for one frequency sweep / batch capture."""

import json
from datetime import datetime
from pathlib import Path


def build_batch_directory(
    root: Path,
    batch_id: str,
    started_at: datetime,
) -> Path:
    if not batch_id.strip():
        raise ValueError("batch_id must not be empty")
    if "/" in batch_id or "\\" in batch_id:
        raise ValueError("batch_id must not contain path separators")

    local_started_at = (
        started_at
        if started_at.tzinfo is None
        else started_at.astimezone()
    )
    return (
        Path(root)
        / "batches"
        / local_started_at.date().isoformat()
        / batch_id
    )


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
