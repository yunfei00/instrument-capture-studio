"""UI-only state models for Instrument Capture Studio.

This module deliberately has no Qt dependency so the state contract can be
unit-tested on development environments that do not provide PySide6.
"""

from dataclasses import dataclass
from enum import Enum


class ConnectionState(str, Enum):
    """Connection state shown by the desktop UI."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class CaptureUiState(str, Enum):
    """High-level capture state shown by the desktop UI."""

    IDLE = "idle"
    RUNNING = "running"
    CANCELING = "canceling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(frozen=True)
class InstrumentPanelState:
    """Presentation state for one instrument connection panel."""

    connection: ConnectionState = ConnectionState.DISCONNECTED
    model: str | None = None
    firmware: str | None = None
    message: str | None = None

    @property
    def is_connected(self) -> bool:
        return self.connection is ConnectionState.CONNECTED


@dataclass(frozen=True)
class CapturePanelState:
    """Presentation state for the capture controls."""

    state: CaptureUiState = CaptureUiState.IDLE
    progress_percent: int = 0
    job_id: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.progress_percent <= 100:
            raise ValueError("progress_percent must be between 0 and 100")

    @property
    def is_busy(self) -> bool:
        return self.state in {
            CaptureUiState.RUNNING,
            CaptureUiState.CANCELING,
        }

    @property
    def can_start(self) -> bool:
        return not self.is_busy

    @property
    def can_stop(self) -> bool:
        return self.state is CaptureUiState.RUNNING
