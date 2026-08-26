from datetime import datetime

from instrument_capture_studio.data.session_log import SessionLogWriter


def test_session_log_writes_timestamped_lines(tmp_path):
    started_at = datetime(2026, 8, 26, 15, 0, 0)
    writer = SessionLogWriter(tmp_path, started_at=started_at)

    writer.append(
        "capture started",
        timestamp=datetime(2026, 8, 26, 15, 0, 1),
    )
    writer.append(
        "capture finished",
        timestamp=datetime(2026, 8, 26, 15, 0, 2),
    )

    assert writer.path.parent.name == "2026-08-26"
    text = writer.path.read_text(encoding="utf-8")
    assert "capture started" in text
    assert "capture finished" in text
    assert text.count("\n") == 2
