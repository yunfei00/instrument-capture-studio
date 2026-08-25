from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from instrument_capture_studio.data.layout import (
    JobDataLayout,
)
from instrument_capture_studio.data.metadata import (
    build_capture_metadata,
    write_capture_metadata,
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

            output_files.append(
                str(
                    layout.spectrum_csv_path
                )
            )

        if context.waveform is not None:
            write_waveform_csv(
                layout.waveform_csv_path,
                context.waveform,
            )

            output_files.append(
                str(
                    layout.waveform_csv_path
                )
            )

        return tuple(
            output_files
        )
