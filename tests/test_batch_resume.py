import json

from instrument_capture_studio.app.batch_capture import (
    BatchState,
    run_frequency_sweep_batch,
)
from instrument_capture_studio.app.frequency_sweep import FrequencySweepPlan
from instrument_capture_studio.app.recovery import RecoveryPolicy
from instrument_capture_studio.core.models import CaptureResult, JobState


class FakeFSW:
    def __init__(self, calls):
        self.calls = calls

    def connect(self):
        self.calls.append(("fsw", "connect"))

    def disconnect(self):
        self.calls.append(("fsw", "disconnect"))

    def configure_frequency(self, center_hz, span_hz):
        self.calls.append(("fsw", "frequency", center_hz, span_hz))


class FakeDSOX:
    def __init__(self, calls):
        self.calls = calls

    def connect(self):
        self.calls.append(("dsox", "connect"))

    def disconnect(self):
        self.calls.append(("dsox", "disconnect"))


def _plan(count=3):
    return FrequencySweepPlan(
        start_hz=700e6,
        stop_hz=700e6,
        step_hz=5e6,
        span_hz=0,
        captures_per_frequency=count,
    )


def _success_runner(calls, on_capture=None):
    def run(fsw, dsox, **kwargs):
        calls.append(kwargs["job_id"])
        if on_capture is not None:
            on_capture(len(calls))
        return CaptureResult(job_id=kwargs["job_id"], state=JobState.SUCCEEDED)

    return run


def test_pause_waits_for_sample_boundary_releases_session_and_resumes(tmp_path):
    instrument_calls = []
    capture_calls = []
    pause_requested = False
    pause_events = []

    def on_capture(number):
        nonlocal pause_requested
        if number == 1:
            pause_requested = True

    def pause_callback(paused, batch_id, completed, total):
        nonlocal pause_requested
        pause_events.append((paused, completed, total))
        if paused:
            pause_requested = False

    result = run_frequency_sweep_batch(
        fsw_factory=lambda: FakeFSW(instrument_calls),
        dsox_factory=lambda: FakeDSOX(instrument_calls),
        plan=_plan(3),
        batch_id="batch-pause",
        output_root=tmp_path,
        pause_check=lambda: pause_requested,
        pause_callback=pause_callback,
        recovery_policy=RecoveryPolicy(max_attempts=2, reconnect_delay_s=0),
        capture_runner=_success_runner(capture_calls, on_capture),
    )

    assert result.state is BatchState.SUCCEEDED
    assert result.completed_captures == 3
    assert capture_calls == [
        "batch-pause-f001-n0001",
        "batch-pause-f001-n0002",
        "batch-pause-f001-n0003",
    ]
    assert pause_events == [(True, 1, 3), (False, 1, 3)]
    assert instrument_calls.count(("fsw", "connect")) == 2
    assert instrument_calls.count(("dsox", "connect")) == 2


def test_canceled_batch_resumes_without_repeating_successful_samples(tmp_path):
    instrument_calls = []
    first_capture_calls = []
    cancel_requested = False

    def on_first_capture(number):
        nonlocal cancel_requested
        if number == 2:
            cancel_requested = True

    first = run_frequency_sweep_batch(
        fsw_factory=lambda: FakeFSW(instrument_calls),
        dsox_factory=lambda: FakeDSOX(instrument_calls),
        plan=_plan(5),
        batch_id="batch-resume",
        output_root=tmp_path,
        cancel_check=lambda: cancel_requested,
        recovery_policy=RecoveryPolicy(max_attempts=2, reconnect_delay_s=0),
        capture_runner=_success_runner(first_capture_calls, on_first_capture),
    )

    assert first.state is BatchState.CANCELED
    assert first.completed_captures == 2

    # Simulate an incomplete directory left by a process crash. Resume must use
    # a new -resumeN Job id instead of overwriting/mixing this directory.
    partial = tmp_path / "2026-08-27" / "batch-resume-f001-n0003"
    partial.mkdir(parents=True, exist_ok=True)
    (partial / "metadata.json").write_text("{}", encoding="utf-8")

    cancel_requested = False
    resumed_capture_calls = []
    resumed = run_frequency_sweep_batch(
        fsw_factory=lambda: FakeFSW(instrument_calls),
        dsox_factory=lambda: FakeDSOX(instrument_calls),
        plan=_plan(5),
        batch_id="batch-resume",
        output_root=tmp_path,
        cancel_check=lambda: False,
        recovery_policy=RecoveryPolicy(max_attempts=2, reconnect_delay_s=0),
        capture_runner=_success_runner(resumed_capture_calls),
        resume_manifest_path=first.manifest_path,
    )

    assert resumed.state is BatchState.SUCCEEDED
    assert resumed.completed_captures == 5
    assert resumed_capture_calls == [
        "batch-resume-f001-n0003-resume1",
        "batch-resume-f001-n0004-resume1",
        "batch-resume-f001-n0005-resume1",
    ]

    manifest = json.loads(open(resumed.manifest_path, encoding="utf-8").read())
    assert manifest["state"] == "succeeded"
    assert manifest["completed_captures"] == 5
    assert manifest["resume_count"] == 1
    assert len(manifest["resume_events"]) == 1
    assert len([job for job in manifest["jobs"] if job["state"] == "succeeded"]) == 5
