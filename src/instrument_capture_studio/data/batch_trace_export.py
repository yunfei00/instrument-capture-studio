"""Export every saved formal paired Recipe trace from a Batch to SVG files."""

import csv
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from instrument_capture_studio.data.batch_manifest import load_batch_manifest
from instrument_capture_studio.data.trace_preview import load_trace_preview
from instrument_capture_studio.reporting.batch_report import render_trace_svg


CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class BatchTraceExportResult:
    output_directory: Path
    index_csv: Path
    exported_files: int
    failed_files: int
    total_files: int
    canceled: bool = False


@dataclass(frozen=True)
class _TraceTask:
    job_id: str
    state: str
    frequency_hz: float | None
    frequency_index: int | None
    capture_index: int | None
    kind: str
    source: Path


_FORMAL_TRACE_FILES = (
    ("spectrum_ext", "spectrum_ext.npz"),
    ("waveform_sync", "waveform_sync.npz"),
    ("waveform_followup", "waveform_followup.npz"),
    ("spectrum_freerun", "spectrum_freerun.npz"),
)


def export_all_batch_traces(
    manifest_path: Path,
    output_directory: Path | None = None,
    *,
    cancel_check: CancelCheck | None = None,
    progress_callback: ProgressCallback | None = None,
) -> BatchTraceExportResult:
    """Export all final paired Recipe NPZ traces referenced by one Batch."""

    manifest_path = Path(manifest_path)
    manifest = load_batch_manifest(manifest_path)
    jobs = manifest.get("jobs")
    jobs = jobs if isinstance(jobs, list) else []

    destination = Path(
        output_directory or manifest_path.parent / "export" / "all_traces"
    )
    for kind, _filename in _FORMAL_TRACE_FILES:
        (destination / kind).mkdir(parents=True, exist_ok=True)

    tasks = _collect_tasks(jobs, manifest_path.parent)
    rows: list[dict[str, object]] = []
    exported_files = 0
    failed_files = 0
    canceled = False

    for completed, task in enumerate(tasks, start=1):
        if cancel_check is not None and cancel_check():
            canceled = True
            break

        target_directory = destination / task.kind
        filename = _export_filename(task)
        target = target_directory / filename
        error = ""

        try:
            preview = load_trace_preview(task.source)
            target.write_text(render_trace_svg(preview), encoding="utf-8")
            exported_files += 1
        except Exception as exc:
            failed_files += 1
            error = f"{type(exc).__name__}: {exc}"

        rows.append(
            {
                "job_id": task.job_id,
                "state": task.state,
                "frequency_hz": "" if task.frequency_hz is None else task.frequency_hz,
                "frequency_index": (
                    "" if task.frequency_index is None else task.frequency_index
                ),
                "capture_index": "" if task.capture_index is None else task.capture_index,
                "kind": task.kind,
                "source": str(task.source),
                "exported": str(target) if not error else "",
                "error": error,
            }
        )

        if progress_callback is not None:
            try:
                progress_callback(completed, len(tasks), task.job_id)
            except Exception:
                pass

    index_csv = destination / "index.csv"
    _write_index(index_csv, rows)

    return BatchTraceExportResult(
        output_directory=destination,
        index_csv=index_csv,
        exported_files=exported_files,
        failed_files=failed_files,
        total_files=len(tasks),
        canceled=canceled,
    )


def _collect_tasks(jobs: list[object], batch_directory: Path) -> list[_TraceTask]:
    tasks: list[_TraceTask] = []

    for raw_record in jobs:
        if not isinstance(raw_record, dict):
            continue

        job_id = str(raw_record.get("job_id") or "unknown-job")
        state = str(raw_record.get("state") or "unknown")
        frequency_hz = _optional_float(raw_record.get("frequency_hz"))
        frequency_index = _optional_int(raw_record.get("frequency_index"))
        capture_index = _optional_int(raw_record.get("capture_index"))
        output_files = raw_record.get("output_files")
        if not isinstance(output_files, list):
            continue

        for kind, filename in _FORMAL_TRACE_FILES:
            source = _find_output_file(output_files, filename, batch_directory)
            if source is None or not source.exists():
                continue
            tasks.append(
                _TraceTask(
                    job_id=job_id,
                    state=state,
                    frequency_hz=frequency_hz,
                    frequency_index=frequency_index,
                    capture_index=capture_index,
                    kind=kind,
                    source=source,
                )
            )

    return tasks


def _find_output_file(
    output_files: list[object],
    filename: str,
    batch_directory: Path,
) -> Path | None:
    for raw_value in output_files:
        path = Path(str(raw_value))
        if path.name != filename:
            continue
        if path.is_absolute():
            return path

        if path.exists():
            return path
        candidates = (
            batch_directory / path,
            batch_directory.parent.parent.parent / path,
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return path
    return None


def _export_filename(task: _TraceTask) -> str:
    frequency_index = task.frequency_index or 0
    capture_index = task.capture_index or 0
    safe_job_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", task.job_id).strip("-._")
    if not safe_job_id:
        safe_job_id = "job"
    return (
        f"f{frequency_index:03d}-n{capture_index:04d}-"
        f"{safe_job_id}-{task.kind}.svg"
    )


def _write_index(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = (
        "job_id",
        "state",
        "frequency_hz",
        "frequency_index",
        "capture_index",
        "kind",
        "source",
        "exported",
        "error",
    )
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _optional_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
