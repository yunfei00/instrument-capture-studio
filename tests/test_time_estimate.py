import json

from instrument_capture_studio.data.time_estimate import estimate_capture_time


def test_estimate_uses_successful_job_wall_clock_durations(tmp_path):
    batch_dir = tmp_path / "batches" / "batch-demo"
    job1 = batch_dir / "f001_700MHz" / "batch-demo-f001-n0001"
    job2 = batch_dir / "f001_700MHz" / "batch-demo-f001-n0002"
    for directory, duration_ms in ((job1, 8000.0), (job2, 10000.0)):
        directory.mkdir(parents=True, exist_ok=True)
        metadata = directory / "metadata.json"
        metadata.write_text("{}", encoding="utf-8")
        (directory / "job.json").write_text(
            json.dumps(
                {
                    "job_id": directory.name,
                    "state": "succeeded",
                    "duration_ms": duration_ms,
                    "steps": [],
                }
            ),
            encoding="utf-8",
        )

    (batch_dir / "batch.json").write_text(
        json.dumps(
            {
                "batch_id": "batch-demo",
                "state": "succeeded",
                "completed_captures": 2,
                "failed_jobs": 0,
                "plan": {
                    "start_hz": 700e6,
                    "stop_hz": 700e6,
                    "step_hz": 1.0,
                    "span_hz": 0.0,
                    "captures_per_frequency": 2,
                    "frequency_count": 1,
                    "total_captures": 2,
                    "frequencies_hz": [700e6],
                },
                "jobs": [
                    {
                        "job_id": job1.name,
                        "state": "succeeded",
                        "frequency_hz": 700e6,
                        "output_files": [str(job1 / "metadata.json")],
                    },
                    {
                        "job_id": job2.name,
                        "state": "succeeded",
                        "frequency_hz": 700e6,
                        "output_files": [str(job2 / "metadata.json")],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    estimate = estimate_capture_time(tmp_path, total_captures=100)
    assert estimate is not None
    assert estimate.samples == 2
    assert estimate.batches == 1
    assert estimate.seconds_per_capture == 9.0
    assert estimate.total_seconds == 900.0
    assert estimate.cycles(55) == 1
