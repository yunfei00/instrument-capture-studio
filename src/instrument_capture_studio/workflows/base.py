from abc import ABC, abstractmethod
from dataclasses import dataclass

from instrument_capture_studio.core.models import CaptureResult


@dataclass(frozen=True)
class CaptureStepDefinition:
    """联合采集流程中一个步骤的定义。"""

    name: str
    timeout_s: float | None = None
    max_retries: int = 0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("step name must not be empty")

        if self.timeout_s is not None and self.timeout_s <= 0:
            raise ValueError("timeout_s must be greater than 0")

        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")


class CaptureWorkflow(ABC):
    """联合采集 Workflow 的基础接口。"""

    @property
    @abstractmethod
    def steps(self) -> tuple[CaptureStepDefinition, ...]:
        """返回 Workflow 中的步骤定义。"""

    @abstractmethod
    def run(self, job_id: str) -> CaptureResult:
        """执行一次完整联合采集任务。"""
