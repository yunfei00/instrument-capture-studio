from datetime import datetime, timezone
from pathlib import Path

from instrument_capture_studio.app.batch_capture import run_frequency_sweep_batch
from instrument_capture_studio.app.frequency_sweep import FrequencySweepPlan
from instrument_capture_studio.core.models import CaptureResult, JobState
from instrument_capture_studio.data.batch_manifest import write_batch_manifest


class _Adapter:
    def connect(self):
        return None

    def disconnect(self):
        return None

    def configure_frequency(self, _frequency_hz, _span_hz):
        return None


def test_resume_uses_frozen_batch_user_fields(tmp_path: Path):
    plan = FrequencySweepPlan(
        start_hz=700e6,
        stop_hz=700e6,
        step_hz=1.0,
        span_hz=0.0,
        captures_per_frequency=1,
    )
    batch_id = "batch-freeze"
    manifest_path = tmp_path / "batches" / batch_id / "batch.json"
    write_batch_manifest(
        manifest_path,
        {
            "schema_version": 1,
            "batch_id": batch_id,
            "state": "failed",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "user_fields": [{"name": "手机型号", "value": "Frozen-A"}],
            "plan": {
                "start_hz": plan.start_hz,
                "stop_hz": plan.stop_hz,
                "step_hz": plan.step_hz,
                "span_hz": plan.span_hz,
                "captures_per_frequency": plan.captures_per_frequency,
                "frequency_count": plan.frequency_count,
                "total_captures": plan.total_captures,
                "frequencies_hz": list(plan.frequencies_hz),
            },
            "completed_captures": 0,
            "failed_jobs": 0,
            "jobs": [],
            "recovery_events": [],
            "resume_events": [],
            "resume_count": 0,
            "cursor": None,
            "last_error": "interrupted",
        },
    )

    captured = []

    def fake_capture(_fsw, _dsox, **kwargs):
        captured.append(kwargs["capture_metadata"])
        now = datetime.now(timezone.utc)
        return CaptureResult(
            job_id=kwargs["job_id"],
            state=JobState.SUCCEEDED,
            started_at=now,
            finished_at=now,
        )

    result = run_frequency_sweep_batch(
        fsw_factory=_Adapter,
        dsox_factory=_Adapter,
        plan=plan,
        batch_id=batch_id,
        output_root=tmp_path,
        capture_runner=fake_capture,
        resume_manifest_path=manifest_path,
        user_fields=[{"name": "手机型号", "value": "Changed-in-GUI"}],
    )

    assert result.state.value == "succeeded"
    assert captured[0]["user_fields"] == [
        {"name": "手机型号", "value": "Frozen-A"}
    ]
