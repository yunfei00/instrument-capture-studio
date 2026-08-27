"""Discovery and validation helpers for resumable Batch capture."""

from dataclasses import dataclass
from pathlib import Path

from instrument_capture_studio.app.frequency_sweep import FrequencySweepPlan
from instrument_capture_studio.data.batch_manifest import load_batch_manifest


_RESUMABLE_STATES = {"running", "paused", "canceled", "failed"}


@dataclass(frozen=True)
class ResumableBatch:
    manifest_path: Path
    batch_id: str
    state: str
    plan: FrequencySweepPlan
    completed_captures: int
    total_captures: int

    @property
    def remaining_captures(self) -> int:
        return max(0, self.total_captures - self.completed_captures)


def _plan_from_payload(payload: dict[str, object]) -> FrequencySweepPlan:
    plan = payload.get("plan")
    if not isinstance(plan, dict):
        raise ValueError("batch manifest is missing plan")
    try:
        return FrequencySweepPlan(
            start_hz=float(plan["start_hz"]),
            stop_hz=float(plan["stop_hz"]),
            step_hz=float(plan["step_hz"]),
            span_hz=float(plan["span_hz"]),
            captures_per_frequency=int(plan["captures_per_frequency"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid batch plan: {exc}") from exc


def load_resumable_batch(path: Path) -> ResumableBatch:
    manifest_path = Path(path).expanduser().resolve()
    if manifest_path.is_dir():
        manifest_path = manifest_path / "batch.json"
    payload = load_batch_manifest(manifest_path)

    batch_id = str(payload.get("batch_id") or "").strip()
    if not batch_id:
        raise ValueError("batch manifest is missing batch_id")
    state = str(payload.get("state") or "unknown").lower()
    plan = _plan_from_payload(payload)
    try:
        completed = int(payload.get("completed_captures") or 0)
    except (TypeError, ValueError):
        completed = 0

    if state not in _RESUMABLE_STATES:
        raise ValueError(f"batch state is not resumable: {state}")
    if completed >= plan.total_captures:
        raise ValueError("batch has no remaining captures")

    return ResumableBatch(
        manifest_path=manifest_path,
        batch_id=batch_id,
        state=state,
        plan=plan,
        completed_captures=completed,
        total_captures=plan.total_captures,
    )


def list_resumable_batches(root: Path, limit: int = 20) -> tuple[ResumableBatch, ...]:
    root = Path(root).expanduser()
    if not root.exists():
        return ()

    candidates: list[tuple[float, Path]] = []
    for path in root.glob("batches/*/*/batch.json"):
        try:
            modified = path.stat().st_mtime
        except OSError:
            continue
        candidates.append((modified, path))
    candidates.sort(key=lambda item: item[0], reverse=True)

    results: list[ResumableBatch] = []
    for _modified, path in candidates:
        try:
            batch = load_resumable_batch(path)
        except (OSError, ValueError):
            continue
        results.append(batch)
        if len(results) >= max(0, limit):
            break
    return tuple(results)


def find_latest_resumable_batch(root: Path) -> ResumableBatch | None:
    batches = list_resumable_batches(root, limit=1)
    return batches[0] if batches else None
