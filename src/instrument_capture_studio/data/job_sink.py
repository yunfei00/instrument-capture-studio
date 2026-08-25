from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from instrument_capture_studio.core.models import (
    CaptureResult,
)
from instrument_capture_studio.data.job_manifest import (
    build_job_manifest,
    write_job_manifest,
)
from instrument_capture_studio.data.layout import (
    JobDataLayout,
)
from instrument_capture_studio.data.metadata import (
    build_capture_metadata,
    write_capture_metadata,
)
from instrument_capture_studio.data.npz import (
    write_spectrum_npz,
    write_waveform_npz,
)
from instrument_capture_studio.data.spectrum_csv import (
    write_spectrum_csv,
)
from instrument_capture_studio.data.waveform_csv import (
    write_waveform_csv,
)
from instrument_capture_studio.workflows.context import (
    CaptureContext,
)


Clock = Callable[[], datetime]


class JobDirectoryResultSink:
    """
    将 Capture Job 保存到标准数据目录。

    Phase 5 当前只写 metadata.json。
    后续会在这里继续加入 CSV / NPZ。
    """

    def __init__(
        self,
        root: Path,
        *,
        clock: Clock | None = None,
    ):
        self._root = Path(root)
        self._clock = (
            clock
            or datetime.now
        )

    def save(
        self,
        job_id: str,
        context: CaptureContext,
    ) -> tuple[str, ...]:
        captured_at = self._clock()

        layout = JobDataLayout.build(
            self._root,
            job_id,
            capture_date=(
                captured_at.date()
            ),
        )

        layout.create_directories()

        metadata = build_capture_metadata(
            job_id,
            context,
            captured_at=captured_at,
        )

        write_capture_metadata(
            layout.metadata_path,
            metadata,
        )

        output_files = [
            str(layout.metadata_path),
        ]

        if context.spectrum is not None:
            write_spectrum_csv(
                layout.spectrum_csv_path,
                context.spectrum,
            )

            write_spectrum_npz(
                layout.spectrum_npz_path,
                context.spectrum,
            )

            output_files.extend(
                (
                    str(
                        layout.spectrum_csv_path
                    ),
                    str(
                        layout.spectrum_npz_path
                    ),
                )
            )

        if context.waveform is not None:
            write_waveform_csv(
                layout.waveform_csv_path,
                context.waveform,
            )

            write_waveform_npz(
                layout.waveform_npz_path,
                context.waveform,
            )

            output_files.extend(
                (
                    str(
                        layout.waveform_csv_path
                    ),
                    str(
                        layout.waveform_npz_path
                    ),
                )
            )

        return tuple(
            output_files
        )

    def save_job(
        self,
        result: CaptureResult,
    ) -> str:
        """
        保存最终 Job 执行清单。

        使用 Job started_at 的本地日期，
        保证运行跨时区时目录日期语义明确。
        """

        if result.started_at is None:
            captured_at = self._clock()
        elif result.started_at.tzinfo is None:
            captured_at = result.started_at
        else:
            captured_at = (
                result.started_at.astimezone()
            )

        layout = JobDataLayout.build(
            self._root,
            result.job_id,
            capture_date=(
                captured_at.date()
            ),
        )

        layout.create_directories()

        manifest = build_job_manifest(
            result
        )

        write_job_manifest(
            layout.job_manifest_path,
            manifest,
        )

        return str(
            layout.job_manifest_path
        )
