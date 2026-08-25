from instrument_capture_studio.core.results import (
    MeasurementResult,
    SpectrumResult,
    WaveformResult,
)
from instrument_capture_studio.workflows.combined import CombinedCaptureWorkflow


class FakeSpectrumAnalyzer:
    def acquire_spectrum(self, *, timeout_s=None, cancel_check=None):
        return SpectrumResult(
            frequencies_hz=[1.0, 2.0],
            amplitudes_dbm=[-10.0, -20.0],
        )


class FakeOscilloscope:
    def acquire_delay(self):
        return MeasurementResult("DELAY", 1e-6, "s")

    def acquire_cycle_count(self):
        return MeasurementResult("CYCLE_COUNT", 3.0, "count")

    def acquire_waveform(self):
        return WaveformResult(
            channel="CH1",
            time_s=[0.0, 1e-6],
            voltage_v=[0.1, 0.2],
            sample_rate_hz=1e6,
        )


class MemorySink:
    def save(self, job_id, context):
        return (f"memory://{job_id}",)


def test_combined_capture_reports_real_step_progress():
    events = []

    workflow = CombinedCaptureWorkflow(
        spectrum_analyzer=FakeSpectrumAnalyzer(),
        oscilloscope=FakeOscilloscope(),
        result_sink=MemorySink(),
        progress_callback=lambda *event: events.append(event),
    )

    result = workflow.run("job-progress")

    assert result.state.value == "succeeded"
    assert events == [
        ("fsw_spectrum", "running", 0, 5),
        ("fsw_spectrum", "succeeded", 1, 5),
        ("dsox_delay", "running", 1, 5),
        ("dsox_delay", "succeeded", 2, 5),
        ("dsox_cycle_count", "running", 2, 5),
        ("dsox_cycle_count", "succeeded", 3, 5),
        ("dsox_waveform", "running", 3, 5),
        ("dsox_waveform", "succeeded", 4, 5),
        ("save_result", "running", 4, 5),
        ("save_result", "succeeded", 5, 5),
    ]


def test_progress_callback_failure_does_not_break_capture():
    def broken_callback(*args):
        raise RuntimeError("UI callback failed")

    workflow = CombinedCaptureWorkflow(
        spectrum_analyzer=FakeSpectrumAnalyzer(),
        oscilloscope=FakeOscilloscope(),
        result_sink=MemorySink(),
        progress_callback=broken_callback,
    )

    result = workflow.run("job-progress-safe")

    assert result.state.value == "succeeded"
