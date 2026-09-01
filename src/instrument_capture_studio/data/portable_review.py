"""Portable post-acquisition review that depends only on final trace files.

Unlike Batch review, directory review intentionally does not require batch.json,
job.json, metadata.json, original absolute paths, or the original acquisition
folder layout. A directory is treated as one reviewable paired sample when it
contains the four formal NPZ traces.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil

from instrument_capture_studio.data.manual_review import FORMAL_REVIEW_TRACES


_REVIEW_DIRECTORY = ".review"
_REVIEW_MANIFEST = "review_manifest.json"
_REJECTED_LOG = "rejected.jsonl"
_FREQUENCY_PATTERN = re.compile(r"(?i)(\d+(?:\.\d+)?)\s*(?:mhz|m)(?:\b|_)?")
_CAPTURE_PATTERN = re.compile(r"(?i)(?:^|[-_])n?(\d{1,8})$")


@dataclass(frozen=True)
class PortableReviewSample:
    """One self-contained paired sample discovered below an arbitrary root."""

    sample_id: str
    relative_path: str
    directory: Path
    frequency_hz: float | None
    capture_index: int | None

    @property
    def trace_paths(self) -> tuple[Path, ...]:
        return tuple(self.directory / name for name in FORMAL_REVIEW_TRACES)


@dataclass(frozen=True)
class PortableReviewScan:
    root: Path
    samples: tuple[PortableReviewSample, ...]
    incomplete_directories: int
    rejected_count: int
    resume_index: int


@dataclass(frozen=True)
class PortableDeleteResult:
    sample_id: str
    directory: Path
    rejected_count: int


def scan_portable_review_samples(root: Path) -> PortableReviewScan:
    """Discover complete paired samples by files instead of acquisition manifests."""

    root = _resolve_root(root)
    candidates: dict[Path, PortableReviewSample] = {}
    incomplete = 0

    # spectrum_ext.npz is the cheapest stable anchor: one per formal paired sample.
    for anchor in root.rglob(FORMAL_REVIEW_TRACES[0]):
        try:
            directory = anchor.parent.resolve()
            relative = directory.relative_to(root)
        except (OSError, ValueError):
            continue
        if _REVIEW_DIRECTORY in relative.parts:
            continue

        missing = [name for name in FORMAL_REVIEW_TRACES if not (directory / name).is_file()]
        if missing:
            incomplete += 1
            continue

        relative_text = relative.as_posix()
        candidates[directory] = PortableReviewSample(
            sample_id=relative_text,
            relative_path=relative_text,
            directory=directory,
            frequency_hz=_infer_frequency_hz(relative.parts),
            capture_index=_infer_capture_index(directory.name),
        )

    samples = sorted(candidates.values(), key=_sample_sort_key)
    state = _load_review_state(root)
    rejected_count = _safe_int(state.get("rejected_count"))
    last_sample = str(state.get("last_sample") or "").strip()
    resume_index = 0
    if samples and last_sample:
        for index, sample in enumerate(samples):
            if sample.relative_path == last_sample:
                resume_index = index
                break

    return PortableReviewScan(
        root=root,
        samples=tuple(samples),
        incomplete_directories=incomplete,
        rejected_count=rejected_count,
        resume_index=resume_index,
    )


def save_portable_review_position(
    root: Path,
    sample: PortableReviewSample | None,
    *,
    position: int | None = None,
    total: int | None = None,
) -> None:
    """Persist a relocatable review cursor using only a path relative to root."""

    root = _resolve_root(root)
    state = _load_review_state(root)
    state.update(
        {
            "schema_version": 1,
            "updated_at": _utc_now(),
            "last_sample": sample.relative_path if sample is not None else None,
        }
    )
    if position is not None:
        state["last_position"] = max(0, int(position))
    if total is not None:
        state["remaining_samples"] = max(0, int(total))
    _write_review_state(root, state)


def reject_portable_review_sample(
    root: Path,
    sample: PortableReviewSample,
) -> PortableDeleteResult:
    """Delete one discovered sample directory without requiring Batch metadata.

    There is intentionally no confirmation step. Safety is enforced by proving
    that the exact target is below the selected root and still contains all four
    formal NPZ traces immediately before deletion.
    """

    root = _resolve_root(root)
    target = Path(sample.directory).expanduser().resolve()
    _validate_portable_delete_target(root, target, sample)

    tombstone = target.with_name(f".{target.name}.review-delete")
    if tombstone.exists():
        raise RuntimeError(f"review delete staging path already exists: {tombstone}")

    target.rename(tombstone)
    now = _utc_now()
    state = _load_review_state(root)
    rejected_count = _safe_int(state.get("rejected_count")) + 1
    state.update(
        {
            "schema_version": 1,
            "updated_at": now,
            "rejected_count": rejected_count,
            "last_deleted_sample": sample.relative_path,
        }
    )

    try:
        _write_review_state(root, state)
    except Exception:
        tombstone.rename(target)
        raise

    shutil.rmtree(tombstone)
    _append_rejected_log(
        root,
        {
            "sample": sample.relative_path,
            "action": "deleted",
            "time": now,
        },
    )
    return PortableDeleteResult(
        sample_id=sample.sample_id,
        directory=target,
        rejected_count=rejected_count,
    )


def _resolve_root(root: Path) -> Path:
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    return root


def _validate_portable_delete_target(
    root: Path,
    target: Path,
    sample: PortableReviewSample,
) -> None:
    try:
        relative = target.relative_to(root)
    except ValueError:
        raise ValueError("refusing to delete: sample is outside the selected data root") from None

    if target == root or not relative.parts:
        raise ValueError("refusing to delete the selected data root")
    if _REVIEW_DIRECTORY in relative.parts:
        raise ValueError("refusing to delete review control data")
    if relative.as_posix() != sample.relative_path:
        raise ValueError("refusing to delete: sample path changed since discovery")
    if not target.is_dir():
        raise FileNotFoundError(str(target))
    missing = [name for name in FORMAL_REVIEW_TRACES if not (target / name).is_file()]
    if missing:
        raise ValueError(
            "refusing to delete: directory is no longer a complete paired sample "
            f"(missing: {', '.join(missing)})"
        )


def _sample_sort_key(sample: PortableReviewSample):
    frequency = sample.frequency_hz if sample.frequency_hz is not None else float("inf")
    capture = sample.capture_index if sample.capture_index is not None else 2**31 - 1
    return (frequency, capture, sample.relative_path.lower())


def _infer_frequency_hz(parts: tuple[str, ...]) -> float | None:
    # Prefer the nearest parent because copied data commonly uses 700MHz/sample_x.
    for text in reversed(parts):
        match = _FREQUENCY_PATTERN.search(text)
        if match is None:
            continue
        try:
            return float(match.group(1)) * 1e6
        except ValueError:
            continue
    return None


def _infer_capture_index(name: str) -> int | None:
    # Native names end in n0001; copied datasets often end in sample_0001.
    native = re.search(r"(?i)(?:^|[-_])n(\d{1,8})$", name)
    if native is not None:
        return int(native.group(1))
    generic = re.search(r"(\d{1,8})$", name)
    if generic is not None:
        return int(generic.group(1))
    return None


def _review_path(root: Path) -> Path:
    return root / _REVIEW_DIRECTORY / _REVIEW_MANIFEST


def _load_review_state(root: Path) -> dict[str, object]:
    path = _review_path(root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "rejected_count": 0}
    return payload if isinstance(payload, dict) else {"schema_version": 1, "rejected_count": 0}


def _write_review_state(root: Path, state: dict[str, object]) -> None:
    directory = root / _REVIEW_DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / _REVIEW_MANIFEST
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _append_rejected_log(root: Path, record: dict[str, object]) -> None:
    directory = root / _REVIEW_DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / _REJECTED_LOG).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
