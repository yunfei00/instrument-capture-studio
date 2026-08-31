import json
from datetime import datetime, timedelta, timezone

from instrument_capture_studio.data.data_browser import (
    list_batch_frequency_groups,
    list_recent_jobs,
)


def test_batch_frequency_index_keeps_more_than_one_hundred_jobs(tmp_path):
    batch_dir = tmp_path / "batches" / "batch-large"
    batch_dir.mkdir(parents=True)
    started = datetime(2026, 8, 31, 1, 0, tzinfo=timezone.utc)

    jobs = []
    for capture_index in range(1, 206):
        finished = started + timedelta(seconds=capture_index)
        jobs.append(
            {
                "job_id": f"batch-large-f001-n{capture_index:04d}",
                "state": "succeeded",
                "frequency_hz": 700e6,
                "frequency_index": 1,
                "capture_index": capture_index,
                "attempt": 1,
                "started_at": (finished - timedelta(seconds=1)).isoformat(),
                "finished_at": finished.isoformat(),
                "output_files": [],
            }
        )
    for capture_index in range(1, 4):
        finished = started + timedelta(seconds=300 + capture_index)
        jobs.append(
            {
                "job_id": f"batch-large-f002-n{capture_index:04d}",
                "state": "succeeded",
                "frequency_hz": 705e6,
                "frequency_index": 2,
                "capture_index": capture_index,
                "attempt": 1,
                "started_at": (finished - timedelta(seconds=1)).isoformat(),
                "finished_at": finished.isoformat(),
                "output_files": [],
            }
        )

    manifest = batch_dir / "batch.json"
    manifest.write_text(
        json.dumps(
            {
                "batch_id": "batch-large",
                "state": "running",
                "plan": {
                    "start_hz": 700e6,
                    "stop_hz": 705e6,
                    "step_hz": 5e6,
                    "span_hz": 0,
                    "captures_per_frequency": 205,
                    "frequency_count": 2,
                    "total_captures": 410,
                    "frequencies_hz": [700e6, 705e6],
                },
                "completed_captures": 208,
                "failed_jobs": 0,
                "jobs": jobs,
            }
        ),
        encoding="utf-8",
    )

    groups = list_batch_frequency_groups(manifest)

    assert len(groups) == 2
    assert groups[0].directory.name == "f001_700MHz"
    assert groups[0].frequency_hz == 700e6
    assert len(groups[0].jobs) == 205
    assert groups[0].jobs[0].capture_index == 1
    assert groups[0].jobs[-1].capture_index == 205
    assert groups[1].directory.name == "f002_705MHz"
    assert len(groups[1].jobs) == 3


def test_recent_job_shortcut_is_bounded_but_batch_index_remains_complete(tmp_path):
    batch_dir = tmp_path / "batches" / "batch-large"
    batch_dir.mkdir(parents=True)
    started = datetime(2026, 8, 31, 1, 0, tzinfo=timezone.utc)
    jobs = []
    for capture_index in range(1, 151):
        finished = started + timedelta(seconds=capture_index)
        jobs.append(
            {
                "job_id": f"batch-large-f001-n{capture_index:04d}",
                "state": "succeeded",
                "frequency_hz": 700e6,
                "frequency_index": 1,
                "capture_index": capture_index,
                "attempt": 1,
                "started_at": (finished - timedelta(seconds=1)).isoformat(),
                "finished_at": finished.isoformat(),
                "output_files": [],
            }
        )

    manifest = batch_dir / "batch.json"
    manifest.write_text(
        json.dumps(
            {
                "batch_id": "batch-large",
                "state": "running",
                "plan": {
                    "start_hz": 700e6,
                    "stop_hz": 700e6,
                    "step_hz": 1,
                    "span_hz": 0,
                    "captures_per_frequency": 150,
                    "frequency_count": 1,
                    "total_captures": 150,
                    "frequencies_hz": [700e6],
                },
                "completed_captures": 150,
                "failed_jobs": 0,
                "jobs": jobs,
            }
        ),
        encoding="utf-8",
    )

    recent = list_recent_jobs(tmp_path, limit=100)
    groups = list_batch_frequency_groups(manifest)

    assert len(recent) == 100
    assert recent[0].job_id.endswith("n0150")
    assert recent[-1].job_id.endswith("n0051")
    assert len(groups[0].jobs) == 150
