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

        return (
            str(layout.metadata_path),
        )
