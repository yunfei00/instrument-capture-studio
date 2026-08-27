import json

from instrument_capture_studio.app.resume import (
    find_latest_resumable_batch,
    load_resumable_batch,
)


def _write_manifest(root, batch_id, *, state, completed, captures=5):
    batch_dir = root / "batches" / "2026-08-27" / batch_id
    batch_dir.mkdir(parents=True)
    path = batch_dir / "batch.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "batch_id": batch_id,
                "state": state,
                "completed_captures": completed,
                "plan": {
                    "start_hz": 700e6,
                    "stop_hz": 700e6,
                    "step_hz": 1.0,
                    "span_hz": 0.0,
                    "captures_per_frequency": captures,
                    "total_captures": captures,
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_loads_canceled_batch_as_resumable(tmp_path):
    path = _write_manifest(
        tmp_path,
        "batch-canceled",
        state="canceled",
        completed=2,
    )

    batch = load_resumable_batch(path)

    assert batch.batch_id == "batch-canceled"
    assert batch.completed_captures == 2
    assert batch.total_captures == 5
    assert batch.remaining_captures == 3
    assert batch.plan.start_hz == 700e6


def test_completed_batch_is_not_discovered(tmp_path):
    _write_manifest(
        tmp_path,
        "batch-done",
        state="succeeded",
        completed=5,
    )

    assert find_latest_resumable_batch(tmp_path) is None


def test_running_manifest_from_crash_is_discovered(tmp_path):
    _write_manifest(
        tmp_path,
        "batch-crashed",
        state="running",
        completed=1,
    )

    batch = find_latest_resumable_batch(tmp_path)

    assert batch is not None
    assert batch.batch_id == "batch-crashed"
    assert batch.state == "running"
    assert batch.remaining_captures == 4
