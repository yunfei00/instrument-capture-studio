import json
from pathlib import Path

from instrument_capture_studio.data.timing import summarize_batch_timings


def _write_job(directory: Path, job_id: str, job_ms: float, step_ms: dict[str, float]):
    directory.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "job_id": job_id,
        "state": "succeeded",
        "duration_ms": job_ms,
        "steps": [
            {
                "name": name,
                "state": "succeeded",
                "duration_ms": duration,
            }
            for name, duration in step_ms.items()
        ],
    }
    (directory / "job.json").write_text(json.dumps(manifest), encoding="utf-8")
    marker = directory / "metadata.json"
    marker.write_text("{}", encoding="utf-8")
    return marker


def test_summarizes_successful_job_and_step_timings(tmp_path):
    root = tmp_path / "data"
    date = "2026-08-27"
    marker1 = _write_job(
        root / date / "job-1",
        "job-1",
        100.0,
        {"fsw_ext_arm": 10.0, "dsox_delay_group": 30.0, "save_result": 5.0},
    )
    marker2 = _write_job(
        root / date / "job-2",
        "job-2",
        200.0,
        {"fsw_ext_arm": 20.0, "dsox_delay_group": 50.0, "save_result": 7.0},
    )

    batch_dir = root / "batches" / date / "batch-demo"
    batch_dir.mkdir(parents=True)
    manifest_path = batch_dir / "batch.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "batch_id": "batch-demo",
                "jobs": [
                    {
                        "job_id": "job-1",
                        "state": "succeeded",
                        "frequency_config_duration_ms": 2.0,
                        "output_files": [str(marker1)],
                    },
                    {
                        "job_id": "job-2",
                        "state": "succeeded",
                        "frequency_config_duration_ms": 4.0,
                        "output_files": [str(marker2)],
                    },
                    {
                        "job_id": "job-failed",
                        "state": "failed",
                        "frequency_config_duration_ms": 9999.0,
                        "output_files": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = summarize_batch_timings(manifest_path)

    assert summary.successful_jobs == 2
    assert summary.job_total is not None
    assert summary.job_total.samples == 2
    assert summary.job_total.average_ms == 150.0
    assert summary.job_total.p95_ms == 195.0
    assert summary.job_total.max_ms == 200.0

    assert summary.frequency_config is not None
    assert summary.frequency_config.average_ms == 3.0
    assert summary.frequency_config.p95_ms == 3.9

    assert summary.steps["fsw_ext_arm"].average_ms == 15.0
    assert summary.steps["dsox_delay_group"].max_ms == 50.0
    assert summary.steps["save_result"].samples == 2
