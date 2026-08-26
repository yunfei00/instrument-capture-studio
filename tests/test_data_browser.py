import json

from instrument_capture_studio.data.data_browser import (
    list_recent_batches,
    list_recent_jobs,
)


def test_lists_batch_and_job_summaries(tmp_path):
    batch_dir = tmp_path / "batches" / "2026-08-26" / "batch-001"
    batch_dir.mkdir(parents=True)
    (batch_dir / "batch.json").write_text(
        json.dumps(
            {
                "batch_id": "batch-001",
                "state": "succeeded",
                "completed_captures": 2100,
                "failed_jobs": 0,
                "plan": {
                    "start_hz": 700e6,
                    "stop_hz": 800e6,
                    "step_hz": 5e6,
                    "captures_per_frequency": 100,
                    "total_captures": 2100,
                },
            }
        ),
        encoding="utf-8",
    )

    job_dir = tmp_path / "2026-08-26" / "capture-001"
    job_dir.mkdir(parents=True)
    (job_dir / "job.json").write_text(
        json.dumps(
            {
                "job_id": "capture-001",
                "state": "succeeded",
            }
        ),
        encoding="utf-8",
    )

    batches = list_recent_batches(tmp_path)
    jobs = list_recent_jobs(tmp_path)

    assert len(batches) == 1
    assert batches[0].batch_id == "batch-001"
    assert batches[0].completed_captures == 2100
    assert batches[0].total_captures == 2100
    assert batches[0].captures_per_frequency == 100

    assert len(jobs) == 1
    assert jobs[0].job_id == "capture-001"
    assert jobs[0].state == "succeeded"
    assert jobs[0].directory == job_dir
