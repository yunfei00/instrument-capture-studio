import json
from datetime import datetime, timezone

from instrument_capture_studio.data.batch_manifest import (
    build_batch_directory,
    format_frequency_directory,
    write_batch_manifest,
)
from instrument_capture_studio.data.job_sink import JobDirectoryResultSink
from instrument_capture_studio.workflows.context import CaptureContext


def test_batch_directory_is_stable_and_not_date_partitioned(tmp_path):
    path = build_batch_directory(
        tmp_path,
        "batch-demo",
        datetime(2026, 8, 31, 23, 59, tzinfo=timezone.utc),
    )
    assert path == tmp_path / "batches" / "batch-demo"


def test_frequency_directory_is_sortable_and_readable():
    assert format_frequency_directory(1, 700e6) == "f001_700MHz"
    assert format_frequency_directory(2, 700.5e6) == "f002_700.5MHz"


def test_batch_job_sink_routes_job_under_frequency_folder(tmp_path):
    batch_directory = tmp_path / "batches" / "batch-demo"
    manifest_path = batch_directory / "batch.json"
    write_batch_manifest(
        manifest_path,
        {
            "batch_id": "batch-demo",
            "plan": {
                "start_hz": 700e6,
                "step_hz": 5e6,
                "frequencies_hz": [700e6, 705e6],
            },
        },
    )

    sink = JobDirectoryResultSink(tmp_path)
    job_id = "batch-demo-f002-n0001"
    sink.begin_job(job_id, datetime(2026, 8, 31, tzinfo=timezone.utc))
    output_files = sink.save(
        job_id,
        CaptureContext(metadata={"recipe": "ext_imm_pair"}),
    )

    metadata_path = batch_directory / "f002_705MHz" / job_id / "metadata.json"
    assert metadata_path.is_file()
    assert str(metadata_path) in output_files
    assert not (tmp_path / "2026-08-31" / job_id).exists()

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["job_id"] == job_id
