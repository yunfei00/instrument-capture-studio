from copy import deepcopy
from typing import Protocol

from instrument_capture_studio.core.models import (
    CaptureResult,
)
from instrument_capture_studio.workflows.context import (
    CaptureContext,
)


class CaptureResultSink(Protocol):
    """Capture Workflow 最终结果的接收端。"""

    def save(
        self,
        job_id: str,
        context: CaptureContext,
    ) -> tuple[str, ...]:
        """
        保存一次完整 Capture Context。

        返回生成的文件或资源路径。
        Phase 4 的内存实现返回空 tuple。
        """
        ...


class CaptureJobManifestSink(Protocol):
    """Capture Job 最终执行结果的接收端。"""

    def save_job(
        self,
        result: CaptureResult,
    ) -> str:
        """保存 job.json，并返回其路径。"""
        ...


class InMemoryResultSink:
    """
    Phase 4 默认结果存储。

    不写磁盘，只保存内存快照。
    Phase 5 可替换为 CSV / NPZ 文件 Sink。
    """

    def __init__(self):
        self._results: dict[
            str,
            CaptureContext,
        ] = {}

    def save(
        self,
        job_id: str,
        context: CaptureContext,
    ) -> tuple[str, ...]:
        self._results[job_id] = deepcopy(
            context
        )

        return ()

    def get(
        self,
        job_id: str,
    ) -> CaptureContext:
        return self._results[job_id]
