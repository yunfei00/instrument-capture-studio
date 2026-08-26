import json

from instrument_capture_studio.app.batch_capture import (
    BatchState,
    run_frequency_sweep_batch,
)
from instrument_capture_studio.app.frequency_sweep import FrequencySweepPlan
from instrument_capture_studio.app.recovery import RecoveryPolicy
from instrument_capture_studio.core.models import (
    CaptureResult,
    JobState,
    StepResult,
    StepState,
)


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


def test_frequency_sweep_reuses_one_instrument_session(tmp_path):
    calls = []

    def capture_runner(fsw, dsox, **kwargs):
        return CaptureResult(
            job_id=kwargs["job_id"],
            state=JobState.SUCCEEDED,
        )

    result = run_frequency_sweep_batch(
        fsw_factory=lambda: FakeFSW(calls),
        dsox_factory=lambda: FakeDSOX(calls),
        plan=FrequencySweepPlan(
            start_hz=700e6,
            stop_hz=710e6,
            step_hz=5e6,
            span_hz=0,
            captures_per_frequency=2,
        ),
        batch_id="batch-long-session",
        output_root=tmp_path,
        recovery_policy=RecoveryPolicy(
            max_attempts=2,
            reconnect_delay_s=0,
        ),
        capture_runner=capture_runner,
    )

    assert result.state is BatchState.SUCCEEDED
    assert result.completed_captures == 6
    assert calls.count(("fsw", "connect")) == 1
    assert calls.count(("dsox", "connect")) == 1
    assert calls.count(("fsw", "disconnect")) == 1
    assert calls.count(("dsox", "disconnect")) == 1

    frequencies = [
        call[2]
        for call in calls
        if call[:2] == ("fsw", "frequency")
    ]
    assert frequencies == [700e6, 700e6, 705e6, 705e6, 710e6, 710e6]

    manifest = json.loads(
        open(result.manifest_path, encoding="utf-8").read()
    )
    assert manifest["state"] == "succeeded"
    assert manifest["completed_captures"] == 6
    assert len(manifest["jobs"]) == 6


def test_frequency_sweep_reconnects_and_retries_same_capture(tmp_path):
    calls = []
    capture_calls = []

    def capture_runner(fsw, dsox, **kwargs):
        capture_calls.append(kwargs["job_id"])
        if len(capture_calls) == 1:
            return CaptureResult(
                job_id=kwargs["job_id"],
                state=JobState.FAILED,
                steps=[
                    StepResult(
                        name="fsw_spectrum",
                        state=StepState.FAILED,
                        error="link lost",
                        metadata={
                            "error_type": "InstrumentCommunicationError",
                        },
                    )
                ],
            )
        return CaptureResult(
            job_id=kwargs["job_id"],
            state=JobState.SUCCEEDED,
        )

    result = run_frequency_sweep_batch(
        fsw_factory=lambda: FakeFSW(calls),
        dsox_factory=lambda: FakeDSOX(calls),
        plan=FrequencySweepPlan(
            start_hz=700e6,
            stop_hz=700e6,
            step_hz=5e6,
            span_hz=10e6,
            captures_per_frequency=1,
        ),
        batch_id="batch-recovery",
        output_root=tmp_path,
        recovery_policy=RecoveryPolicy(
            max_attempts=2,
            reconnect_delay_s=0,
        ),
        capture_runner=capture_runner,
    )

    assert result.state is BatchState.SUCCEEDED
    assert result.completed_captures == 1
    assert result.failed_jobs == 1
    assert capture_calls == [
        "batch-recovery-f001-n0001",
        "batch-recovery-f001-n0001-retry2",
    ]
    assert calls.count(("fsw", "connect")) == 2
    assert calls.count(("dsox", "connect")) == 2

    manifest = json.loads(
        open(result.manifest_path, encoding="utf-8").read()
    )
    assert len(manifest["jobs"]) == 2
    assert len(manifest["recovery_events"]) == 1
    assert manifest["jobs"][0]["state"] == "failed"
    assert manifest["jobs"][1]["state"] == "succeeded"
