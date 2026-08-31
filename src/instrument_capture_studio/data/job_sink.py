from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
import re

from instrument_capture_studio.core.models import CaptureResult
from instrument_capture_studio.data.batch_manifest import (
    format_frequency_directory,
    load_batch_manifest,
)
from instrument_capture_studio.data.job_manifest import (
    build_job_manifest,
    write_job_manifest,
)
from instrument_capture_studio.data.layout import JobDataLayout
from instrument_capture_studio.data.metadata import (
    build_capture_metadata,
    write_capture_metadata,
)
from instrument_capture_studio.data.npz import (
    write_spectrum_npz,
    write_waveform_npz,
)
from instrument_capture_studio.data.spectrum_csv import write_spectrum_csv
from instrument_capture_studio.data.waveform_csv import write_waveform_csv
from instrument_capture_studio.workflows.context import CaptureContext


Clock = Callable[[], datetime]
_BATCH_JOB_PATTERN = re.compile(
    r"^(?P<batch_id>batch-.+)-f(?P<frequency_index>\d+)-n\d+"
)


class JobDirectoryResultSink:
    """Persist Capture Jobs using explicit recipe artifact names.

    Standalone jobs retain the v1 date-based layout. Batch jobs are routed
    automatically beneath their stable Batch directory and grouped by frequency,
    for example ``batches/batch-abc/f001_700MHz/<job-id>``. This keeps a long
    sweep together even when it runs across midnight or resumes on another day.
    """

    def __init__(self, root: Path, *, clock: Clock | None = None):
        self._root = Path(root)
        self._clock = clock or datetime.now
        self._job_dates: dict[str, date] = {}
        self._job_storage_roots: dict[str, Path] = {}

    def begin_job(self, job_id: str, started_at: datetime) -> None:
        local_started_at = (
            started_at if started_at.tzinfo is None else started_at.astimezone()
        )
        self._job_dates[job_id] = local_started_at.date()
        batch_root = self._resolve_batch_frequency_root(job_id)
        if batch_root is not None:
            self._job_storage_roots[job_id] = batch_root

    def _layout(self, job_id: str, captured_at: datetime) -> JobDataLayout:
        storage_root = self._job_storage_roots.get(job_id)
        if storage_root is None:
            storage_root = self._resolve_batch_frequency_root(job_id)
            if storage_root is not None:
                self._job_storage_roots[job_id] = storage_root

        if storage_root is not None:
            return JobDataLayout.build(
                storage_root,
                job_id,
                capture_date=self._job_dates.get(job_id, captured_at.date()),
                use_date_directory=False,
            )

        return JobDataLayout.build(
            self._root,
            job_id,
            capture_date=self._job_dates.get(job_id, captured_at.date()),
        )

    def _resolve_batch_frequency_root(self, job_id: str) -> Path | None:
        match = _BATCH_JOB_PATTERN.match(job_id)
        if match is None:
            return None

        batch_id = match.group("batch_id")
        frequency_index = int(match.group("frequency_index"))
        manifests = [self._root / "batches" / batch_id / "batch.json"]
        manifests.extend(
            self._root.glob(f"batches/*/{batch_id}/batch.json")
        )

        manifest_path = next((path for path in manifests if path.is_file()), None)
        if manifest_path is None:
            return None

        try:
            manifest = load_batch_manifest(manifest_path)
        except (OSError, ValueError):
            return None
        plan = manifest.get("plan")
        if not isinstance(plan, dict):
            return None

        frequency_hz: float | None = None
        values = plan.get("frequencies_hz")
        if isinstance(values, list) and 0 < frequency_index <= len(values):
            try:
                frequency_hz = float(values[frequency_index - 1])
            except (TypeError, ValueError):
                frequency_hz = None
        if frequency_hz is None:
            try:
                start_hz = float(plan["start_hz"])
                step_hz = float(plan["step_hz"])
                frequency_hz = start_hz + (frequency_index - 1) * step_hz
            except (KeyError, TypeError, ValueError):
                return None

        return manifest_path.parent / format_frequency_directory(
            frequency_index,
            frequency_hz,
        )

    def save(self, job_id: str, context: CaptureContext) -> tuple[str, ...]:
        captured_at = self._clock()
        layout = self._layout(job_id, captured_at)
        layout.create_directories()

        metadata = build_capture_metadata(
            job_id,
            context,
            captured_at=captured_at,
        )
        write_capture_metadata(layout.metadata_path, metadata)
        output_files = [str(layout.metadata_path)]

        # Internal legacy/debug artifacts.
        if context.spectrum is not None:
            write_spectrum_csv(layout.spectrum_csv_path, context.spectrum)
            write_spectrum_npz(layout.spectrum_npz_path, context.spectrum)
            output_files.extend(
                (str(layout.spectrum_csv_path), str(layout.spectrum_npz_path))
            )
        if context.waveform is not None:
            write_waveform_csv(layout.waveform_csv_path, context.waveform)
            write_waveform_npz(layout.waveform_npz_path, context.waveform)
            output_files.extend(
                (str(layout.waveform_csv_path), str(layout.waveform_npz_path))
            )

        # Final paired recipe artifacts.
        if context.spectrum_ext is not None:
            write_spectrum_csv(layout.spectrum_ext_csv_path, context.spectrum_ext)
            write_spectrum_npz(layout.spectrum_ext_npz_path, context.spectrum_ext)
            output_files.extend(
                (str(layout.spectrum_ext_csv_path), str(layout.spectrum_ext_npz_path))
            )
        if context.waveform_sync is not None:
            write_waveform_csv(layout.waveform_sync_csv_path, context.waveform_sync)
            write_waveform_npz(layout.waveform_sync_npz_path, context.waveform_sync)
            output_files.extend(
                (str(layout.waveform_sync_csv_path), str(layout.waveform_sync_npz_path))
            )
        if context.waveform_followup is not None:
            write_waveform_csv(
                layout.waveform_followup_csv_path,
                context.waveform_followup,
            )
            write_waveform_npz(
                layout.waveform_followup_npz_path,
                context.waveform_followup,
            )
            output_files.extend(
                (
                    str(layout.waveform_followup_csv_path),
                    str(layout.waveform_followup_npz_path),
                )
            )
        if context.spectrum_freerun is not None:
            write_spectrum_csv(
                layout.spectrum_freerun_csv_path,
                context.spectrum_freerun,
            )
            write_spectrum_npz(
                layout.spectrum_freerun_npz_path,
                context.spectrum_freerun,
            )
            output_files.extend(
                (
                    str(layout.spectrum_freerun_csv_path),
                    str(layout.spectrum_freerun_npz_path),
                )
            )

        # Standalone v1 recipes.
        if context.spectrum_imm is not None:
            write_spectrum_csv(layout.spectrum_imm_csv_path, context.spectrum_imm)
            write_spectrum_npz(layout.spectrum_imm_npz_path, context.spectrum_imm)
            output_files.extend(
                (str(layout.spectrum_imm_csv_path), str(layout.spectrum_imm_npz_path))
            )
        if context.waveform_delay is not None:
            write_waveform_csv(layout.waveform_delay_csv_path, context.waveform_delay)
            write_waveform_npz(layout.waveform_delay_npz_path, context.waveform_delay)
            output_files.extend(
                (str(layout.waveform_delay_csv_path), str(layout.waveform_delay_npz_path))
            )
        if context.waveform_cycle is not None:
            write_waveform_csv(layout.waveform_cycle_csv_path, context.waveform_cycle)
            write_waveform_npz(layout.waveform_cycle_npz_path, context.waveform_cycle)
            output_files.extend(
                (str(layout.waveform_cycle_csv_path), str(layout.waveform_cycle_npz_path))
            )

        return tuple(output_files)

    def save_job(self, result: CaptureResult) -> str:
        """Persist the final Job execution manifest."""
        if result.started_at is None:
            captured_at = self._clock()
        elif result.started_at.tzinfo is None:
            captured_at = result.started_at
        else:
            captured_at = result.started_at.astimezone()

        layout = self._layout(result.job_id, captured_at)
        layout.create_directories()
        manifest = build_job_manifest(result)
        write_job_manifest(layout.job_manifest_path, manifest)
        return str(layout.job_manifest_path)
