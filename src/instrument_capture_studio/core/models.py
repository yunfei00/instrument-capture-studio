from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class InstrumentState(str, Enum):
    """仪表连接与运行状态。"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    BUSY = "busy"
    ERROR = "error"


class JobState(str, Enum):
    """一次完整 Capture Job 的状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class StepState(str, Enum):
    """Capture Job 中单个 Step 的状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELED = "canceled"


@dataclass
class InstrumentStatus:
    """产品层看到的仪表状态。"""

    name: str
    address: str
    state: InstrumentState = InstrumentState.DISCONNECTED
    model: str | None = None
    serial_number: str | None = None
    firmware_version: str | None = None
    last_error: str | None = None


@dataclass
class StepResult:
    """联合采集流程中一个步骤的执行结果。"""

    name: str
    state: StepState = StepState.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CaptureResult:
    """一次完整联合采集任务的结果。"""

    job_id: str
    state: JobState = JobState.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    steps: list[StepResult] = field(default_factory=list)
    output_files: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
