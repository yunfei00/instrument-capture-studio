import json
from pathlib import Path

import pytest

from instrument_capture_studio.data.batch_manifest import write_batch_manifest
from instrument_capture_studio.data.manual_review import (
    list_review_samples,
    reject_review_sample,
)


def _build_batch(tmp_path: Path, *, state: str = "succeeded") -> tuple[Path, Path]:
    batch = tmp_path / "batches" / "batch-review"
    job_id = "batch-review-f001-n0001"
    job_dir = batch / "f001_700MHz" / job_id
    job_dir.mkdir(parents=True)
    for name in (
        "spectrum_ext.npz",
        "waveform_sync.npz",
        "waveform_followup.npz",
        "spectrum_freerun.npz",
        "metadata.json",
        "job.json",
    ):
        (job_dir / name).write_bytes(b"placeholder")

    manifest_path = batch / "batch.json"
    manifest = {
        "schema_version": 1,
        "batch_id": "batch-review",
        "state": state,
        "completed_captures": 1,
        "failed_jobs": 0,
        "plan": {
            "start_hz": 700e6,
            "stop_hz": 700e6,
            "step_hz": 5e6,
            "span_hz": 0.0,
            "captures_per_frequency": 1,
            "frequency_count": 1,
            "total_captures": 1,
            "frequencies_hz": [700e6],
        },
        "jobs": [
            {
                "job_id": job_id,
                "state": "succeeded",
                "frequency_hz": 700e6,
                "frequency_index": 1,
                "capture_index": 1,
                "attempt": 1,
                "output_files": [str(job_dir / "spectrum_ext.npz")],
            }
        ],
    }
    write_batch_manifest(manifest_path, manifest)
    return manifest_path, job_dir


def test_reject_review_sample_deletes_whole_job_and_keeps_audit(tmp_path: Path):
    manifest_path, job_dir = _build_batch(tmp_path)

    samples = list_review_samples(manifest_path)
    assert len(samples) == 1
    assert samples[0].directory == job_dir

    result = reject_review_sample(manifest_path, samples[0].job_id)

    assert not job_dir.exists()
    assert result.rejected_count == 1
    assert list_review_samples(manifest_path) == ()

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = payload["jobs"][0]
    assert record["state"] == "succeeded"
    assert record["review_status"] == "rejected"
    assert record["review_reason"] == "manual_screening"
    assert record["output_files"] == []
    assert record["review_deleted_output_files"]
    assert payload["completed_captures"] == 1
    assert payload["review_summary"]["rejected_count"] == 1
    assert payload["review_summary"]["remaining_successful_samples"] == 0


def test_reject_review_sample_refuses_running_batch(tmp_path: Path):
    manifest_path, job_dir = _build_batch(tmp_path, state="running")

    with pytest.raises(RuntimeError, match="不允许人工删除"):
        reject_review_sample(manifest_path, "batch-review-f001-n0001")

    assert job_dir.is_dir()
