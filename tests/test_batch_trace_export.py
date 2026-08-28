import json
from pathlib import Path

import numpy as np

from instrument_capture_studio.data.batch_trace_export import (
    export_all_batch_traces,
)


def _save_spectrum(path: Path, center_hz: float, level: float) -> None:
    np.savez_compressed(
        path,
        frequency_hz=np.array([center_hz - 1e6, center_hz, center_hz + 1e6]),
        amplitude_dbm=np.array([level - 5, level, level - 3]),
    )


def _save_waveform(path: Path, scale: float) -> None:
    np.savez_compressed(
        path,
        time_s=np.array([0.0, scale, 2 * scale]),
        voltage_v=np.array([0.0, 1.0, 0.0]),
    )


def test_export_all_batch_traces(tmp_path: Path):
    data_root = tmp_path / "data"
    job_directory = data_root / "2026-08-28" / "job-1"
    job_directory.mkdir(parents=True)

    files = {
        "spectrum_ext": job_directory / "spectrum_ext.npz",
        "waveform_sync": job_directory / "waveform_sync.npz",
        "waveform_followup": job_directory / "waveform_followup.npz",
        "spectrum_freerun": job_directory / "spectrum_freerun.npz",
    }
    _save_spectrum(files["spectrum_ext"], 700e6, -55.0)
    _save_waveform(files["waveform_sync"], 2e-6)
    _save_waveform(files["waveform_followup"], 20e-9)
    _save_spectrum(files["spectrum_freerun"], 700e6, -65.0)

    batch_directory = data_root / "batches" / "2026-08-28" / "batch-1"
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
                        "output_files": [str(path) for path in files.values()],
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
    assert result.total_files == 4
    assert result.exported_files == 4
    assert result.failed_files == 0
    assert result.index_csv.exists()
    for kind in files:
        assert len(list((result.output_directory / kind).glob("*.svg"))) == 1
    assert progress == [
        (1, 4, "batch-1-f001-n0001"),
        (2, 4, "batch-1-f001-n0001"),
        (3, 4, "batch-1-f001-n0001"),
        (4, 4, "batch-1-f001-n0001"),
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
