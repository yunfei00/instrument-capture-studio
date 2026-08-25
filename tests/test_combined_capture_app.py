import subprocess
import sys
from pathlib import Path

import pytest

from instrument_capture_studio.app.combined_capture import (
    run_combined_capture,
)
from instrument_capture_studio.core.models import (
    JobState,
)
from instrument_capture_studio.core.results import (
    MeasurementResult,
    SpectrumResult,
    WaveformResult,
)


class FakeSpectrumAnalyzer:
    name = "FSW"

    def __init__(
        self,
        calls,
    ):
        self.calls = calls

    def connect(self):
        self.calls.append(
            "fsw_connect"
        )

    def disconnect(self):
        self.calls.append(
            "fsw_disconnect"
        )

    def acquire_spectrum(
        self,
        *,
        timeout_s=None,
        cancel_check=None,
    ):
        self.calls.append(
            "fsw_spectrum"
        )

        return SpectrumResult(
            frequencies_hz=[
                1.0,
                2.0,
            ],
            amplitudes_dbm=[
                -20.0,
                -10.0,
            ],
        )


class FakeOscilloscope:
    name = "DSO-X"

    def __init__(
        self,
        calls,
        *,
        fail_connect=False,
    ):
        self.calls = calls
        self.fail_connect = (
            fail_connect
        )

    def connect(self):
        self.calls.append(
            "dsox_connect"
        )

        if self.fail_connect:
            raise RuntimeError(
                "DSO-X connection failed"
            )

    def disconnect(self):
        self.calls.append(
            "dsox_disconnect"
        )

    def acquire_delay(self):
        self.calls.append(
            "dsox_delay"
        )

        return MeasurementResult(
            measurement="DELAY",
            value=1e-6,
            unit="s",
        )

    def acquire_cycle_count(self):
        self.calls.append(
            "dsox_cycle_count"
        )

        return MeasurementResult(
            measurement="CYCLE_COUNT",
            value=10,
            unit="count",
        )

    def acquire_waveform(self):
        self.calls.append(
            "dsox_waveform"
        )

        return WaveformResult(
            channel="CH1",
            time_s=[
                0.0,
                1e-6,
            ],
            voltage_v=[
                0.0,
                1.0,
            ],
        )


def test_app_runs_complete_connected_capture():
    calls = []

    result = run_combined_capture(
        FakeSpectrumAnalyzer(
            calls
        ),
        FakeOscilloscope(
            calls
        ),
        job_id="job-app",
        fsw_timeout_s=5.0,
    )

    assert (
        result.state
        == JobState.SUCCEEDED
    )

    assert (
        result.metadata[
            "capture_complete"
        ]
        is True
    )

    assert (
        result.metadata[
            "result_saved"
        ]
        is True
    )

    assert calls == [
        "fsw_connect",
        "dsox_connect",
        "fsw_spectrum",
        "dsox_delay",
        "dsox_cycle_count",
        "dsox_waveform",
        "dsox_disconnect",
        "fsw_disconnect",
    ]


def test_app_disconnects_fsw_if_dsox_connect_fails():
    calls = []

    with pytest.raises(
        RuntimeError,
        match="DSO-X connection failed",
    ):
        run_combined_capture(
            FakeSpectrumAnalyzer(
                calls
            ),
            FakeOscilloscope(
                calls,
                fail_connect=True,
            ),
            job_id="job-connect-fail",
        )

    assert calls == [
        "fsw_connect",
        "dsox_connect",
        "fsw_disconnect",
    ]


def test_combined_capture_script_has_cli_help():
    root = (
        Path(__file__)
        .resolve()
        .parents[1]
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_combined_capture.py",
            "--help",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0

    assert (
        "--fsw-resource"
        in completed.stdout
    )

    assert (
        "--dsox-resource"
        in completed.stdout
    )


class RecordingJobManifestSink:
    def __init__(self):
        self.results = []

    def save_job(
        self,
        result,
    ):
        self.results.append(
            result
        )

        return (
            f"memory://{result.job_id}/job.json"
        )


def test_app_records_successful_job_manifest():
    calls = []

    manifest_sink = (
        RecordingJobManifestSink()
    )

    result = run_combined_capture(
        FakeSpectrumAnalyzer(
            calls
        ),
        FakeOscilloscope(
            calls
        ),
        job_id="job-manifest-success",
        job_manifest_sink=manifest_sink,
    )

    assert (
        result.state
        == JobState.SUCCEEDED
    )

    assert manifest_sink.results == [
        result
    ]


def test_app_records_failed_job_manifest():
    from instrument_capture_studio.core.exceptions import (
        InstrumentCommunicationError,
    )

    class FailingSpectrumAnalyzer(
        FakeSpectrumAnalyzer
    ):
        def acquire_spectrum(
            self,
            *,
            timeout_s=None,
            cancel_check=None,
        ):
            raise InstrumentCommunicationError(
                "FSW communication failed"
            )

    calls = []

    manifest_sink = (
        RecordingJobManifestSink()
    )

    result = run_combined_capture(
        FailingSpectrumAnalyzer(
            calls
        ),
        FakeOscilloscope(
            calls
        ),
        job_id="job-manifest-failed",
        job_manifest_sink=manifest_sink,
    )

    assert (
        result.state
        == JobState.FAILED
    )

    assert manifest_sink.results == [
        result
    ]

    assert (
        result.steps[0].error
        == "FSW communication failed"
    )


def test_app_records_canceled_job_manifest():
    calls = []

    manifest_sink = (
        RecordingJobManifestSink()
    )

    result = run_combined_capture(
        FakeSpectrumAnalyzer(
            calls
        ),
        FakeOscilloscope(
            calls
        ),
        job_id="job-manifest-canceled",
        cancel_check=lambda: True,
        job_manifest_sink=manifest_sink,
    )

    assert (
        result.state
        == JobState.CANCELED
    )

    assert manifest_sink.results == [
        result
    ]


def test_app_records_fsw_connection_failure_manifest():
    class FailingSpectrumAnalyzer(
        FakeSpectrumAnalyzer
    ):
        def connect(self):
            self.calls.append(
                "fsw_connect"
            )

            raise RuntimeError(
                "FSW connection failed"
            )

    calls = []

    manifest_sink = (
        RecordingJobManifestSink()
    )

    with pytest.raises(
        RuntimeError,
        match="FSW connection failed",
    ):
        run_combined_capture(
            FailingSpectrumAnalyzer(
                calls
            ),
            FakeOscilloscope(
                calls
            ),
            job_id="job-fsw-connect-fail",
            job_manifest_sink=manifest_sink,
        )

    assert calls == [
        "fsw_connect",
    ]

    assert len(
        manifest_sink.results
    ) == 1

    result = (
        manifest_sink.results[0]
    )

    assert (
        result.state
        == JobState.FAILED
    )

    error = result.metadata[
        "application_error"
    ]

    assert error[
        "stage"
    ] == "connect_spectrum_analyzer"

    assert error[
        "instrument"
    ] == "FSW"

    assert error[
        "error_type"
    ] == "RuntimeError"

    assert error[
        "message"
    ] == "FSW connection failed"


def test_app_records_dsox_connection_failure_manifest():
    calls = []

    manifest_sink = (
        RecordingJobManifestSink()
    )

    with pytest.raises(
        RuntimeError,
        match="DSO-X connection failed",
    ):
        run_combined_capture(
            FakeSpectrumAnalyzer(
                calls
            ),
            FakeOscilloscope(
                calls,
                fail_connect=True,
            ),
            job_id="job-dsox-connect-fail",
            job_manifest_sink=manifest_sink,
        )

    assert calls == [
        "fsw_connect",
        "dsox_connect",
        "fsw_disconnect",
    ]

    assert len(
        manifest_sink.results
    ) == 1

    result = (
        manifest_sink.results[0]
    )

    assert (
        result.state
        == JobState.FAILED
    )

    error = result.metadata[
        "application_error"
    ]

    assert error[
        "stage"
    ] == "connect_oscilloscope"

    assert error[
        "instrument"
    ] == "DSO-X"

    assert error[
        "error_type"
    ] == "RuntimeError"

    assert error[
        "message"
    ] == "DSO-X connection failed"
