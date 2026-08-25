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
