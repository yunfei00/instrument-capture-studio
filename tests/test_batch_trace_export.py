import json
from pathlib import Path

import numpy as np

from instrument_capture_studio.data.batch_trace_export import (
    export_all_batch_traces,
)


def test_export_all_batch_traces(tmp_path: Path):
    data_root = tmp_path / "data"
    job_directory = data_root / "2026-08-26" / "job-1"
    job_directory.mkdir(parents=True)

    spectrum = job_directory / "spectrum.npz"
    waveform = job_directory / "waveform.npz"
    np.savez_compressed(
        spectrum,
        frequency_hz=np.array([700e6, 700.5e6, 701e6]),
        amplitude_dbm=np.array([-80.0, -55.0, -70.0]),
    )
    np.savez_compressed(
        waveform,
        time_s=np.array([0.0, 1e-6, 2e-6]),
        voltage_v=np.array([0.0, 1.0, 0.0]),
    )

    batch_directory = data_root / "batches" / "2026-08-26" / "batch-1"
    batch_directory.mkdir(parents=True)
    manifest_path = batch_directory / "batch.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "batch_id": "batch-1",
                "jobs": [
                    {
                        "job_id": "batch-1-f001-n0001",
                        "state": "succeeded",
                        "frequency_hz": 700e6,
                        "frequency_index": 1,
                        "capture_index": 1,
                        "output_files": [str(spectrum), str(waveform)],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    progress = []
    result = export_all_batch_traces(
        manifest_path,
        progress_callback=lambda completed, total, job_id: progress.append(
            (completed, total, job_id)
        ),
    )

    assert result.canceled is False
    assert result.total_files == 2
    assert result.exported_files == 2
    assert result.failed_files == 0
    assert result.index_csv.exists()
    assert len(list((result.output_directory / "spectrum").glob("*.svg"))) == 1
    assert len(list((result.output_directory / "waveform").glob("*.svg"))) == 1
    assert progress == [
        (1, 2, "batch-1-f001-n0001"),
        (2, 2, "batch-1-f001-n0001"),
    ]


def test_export_all_batch_traces_can_cancel(tmp_path: Path):
    batch_directory = tmp_path / "batch"
    batch_directory.mkdir()
    manifest_path = batch_directory / "batch.json"
    manifest_path.write_text(
        json.dumps({"schema_version": 1, "batch_id": "batch-1", "jobs": []}),
        encoding="utf-8",
    )

    result = export_all_batch_traces(
        manifest_path,
        cancel_check=lambda: True,
    )

    assert result.exported_files == 0
    assert result.total_files == 0
    assert result.canceled is False
