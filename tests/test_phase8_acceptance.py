import json
from pathlib import Path

from instrument_capture_studio.data.acceptance import validate_batch_artifacts


_STANDARD_FILES = (
    "job.json",
    "metadata.json",
    "spectrum.csv",
    "spectrum.npz",
    "waveform.csv",
    "waveform.npz",
)


def _make_batch(tmp_path: Path, *, missing: str | None = None) -> Path:
    root = tmp_path / "data"
    job_id = "batch-demo-f001-n0001"
    job_dir = root / "2026-08-26" / job_id
    job_dir.mkdir(parents=True)
    for filename in _STANDARD_FILES:
        if filename != missing:
            (job_dir / filename).write_text("{}", encoding="utf-8")

    batch_dir = root / "batches" / "2026-08-26" / "batch-demo"
    batch_dir.mkdir(parents=True)
    manifest = {
        "batch_id": "batch-demo",
        "state": "succeeded",
        "plan": {"total_captures": 1},
        "completed_captures": 1,
        "failed_jobs": 0,
        "jobs": [
            {
                "job_id": job_id,
                "state": "succeeded",
                "output_files": [str(job_dir / "metadata.json")],
            }
        ],
        "recovery_events": [],
    }
    manifest_path = batch_dir / "batch.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_batch_acceptance_passes_with_all_six_standard_files(tmp_path):
    report = validate_batch_artifacts(_make_batch(tmp_path))

    assert report.passed is True
    assert report.completed_captures == 1
    assert report.successful_jobs == 1
    assert report.missing_files == ()


def test_batch_acceptance_reports_missing_standard_file(tmp_path):
    report = validate_batch_artifacts(
        _make_batch(tmp_path, missing="waveform.npz")
    )

    assert report.passed is False
    assert report.missing_files == (
        "batch-demo-f001-n0001: waveform.npz",
    )
