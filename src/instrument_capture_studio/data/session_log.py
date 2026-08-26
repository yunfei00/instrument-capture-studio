"""Persistent text logs for long-running desktop acquisition sessions."""

from datetime import datetime
from pathlib import Path
from threading import Lock


class SessionLogWriter:
    """Append timestamped GUI/runtime messages to one session log file."""

    def __init__(self, root: Path, *, started_at: datetime | None = None) -> None:
        self._root = Path(root)
        self._started_at = started_at or datetime.now().astimezone()
        self._lock = Lock()

        day_directory = self._root / self._started_at.date().isoformat()
        day_directory.mkdir(parents=True, exist_ok=True)
        filename = self._started_at.strftime("session-%H%M%S-%f.log")
        self._path = day_directory / filename
        self._path.touch(exist_ok=False)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, message: str, *, timestamp: datetime | None = None) -> None:
        current = timestamp or datetime.now().astimezone()
        line = f"{current.isoformat(timespec='milliseconds')} | {message}\n"
        with self._lock:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()


def default_session_log_directory() -> Path:
    return Path.home() / "InstrumentCaptureStudio" / "logs"
