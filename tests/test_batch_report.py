import json

import numpy as np

from instrument_capture_studio.reporting.batch_report import export_batch_report


def _job_files(job_dir, frequency_hz):
    job_dir.mkdir(parents=True)
    spectrum = job_dir / "spectrum.npz"
    waveform = job_dir / "waveform.npz"
    np.savez_compressed(
        spectrum,
        frequency_hz=np.array([frequency_hz - 1e6, frequency_hz, frequency_hz + 1e6]),
        amplitude_dbm=np.array([-80.0, -40.0, -70.0]),
    )
    np.savez_compressed(
        waveform,
        time_s=np.array([0.0, 1e-6, 2e-6]),
        voltage_v=np.array([0.0, 1.0, 0.0]),
    )
    return [str(spectrum), str(waveform)]


def test_exports_large_batch_summary_with_representative_plots(tmp_path):
    batch_dir = tmp_path / "batches" / "2026-08-26" / "batch-001"
    batch_dir.mkdir(parents=True)

    jobs = []
    for index, frequency_hz in enumerate((700e6, 705e6), start=1):
        job_dir = tmp_path / "2026-08-26" / f"capture-{index:03d}"
        jobs.append(
            {
                "job_id": job_dir.name,
                "state": "succeeded",
                "frequency_hz": frequency_hz,
                "frequency_index": index,
                "capture_index": 1,
                "attempt": 1,
                "started_at": "2026-08-26T00:00:00+00:00",
                "finished_at": "2026-08-26T00:00:01+00:00",
                "error": None,
                "output_files": _job_files(job_dir, frequency_hz),
            }
        )

    manifest_path = batch_dir / "batch.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "batch_id": "batch-001",
                "state": "succeeded",
                "started_at": "2026-08-26T00:00:00+00:00",
                "finished_at": "2026-08-26T00:00:02+00:00",
                "completed_captures": 2,
                "failed_jobs": 0,
                "recovery_events": [],
                "plan": {
                    "start_hz": 700e6,
                    "stop_hz": 705e6,
                    "step_hz": 5e6,
                    "span_hz": 0,
                    "captures_per_frequency": 1,
                    "frequency_count": 2,
                    "total_captures": 2,
                    "frequencies_hz": [700e6, 705e6],
                },
                "jobs": jobs,
            }
        ),
        encoding="utf-8",
    )

    result = export_batch_report(manifest_path)

    assert result.report_html.exists()
    assert result.jobs_csv.exists()
    assert result.asset_count == 4

    html = result.report_html.read_text(encoding="utf-8")
    assert "batch-001" in html
    assert "700" in html
    assert "705" in html
    assert "jobs.csv" in html

    assets = sorted((result.report_html.parent / "assets").glob("*.svg"))
    assert len(assets) == 4
    assert all("<svg" in path.read_text(encoding="utf-8") for path in assets)
