from instrument_capture_studio.core.results import (
    MeasurementResult,
    SpectrumResult,
    WaveformResult,
)
from instrument_capture_studio.workflows.context import (
    CaptureContext,
)


def test_capture_context_starts_empty():
    context = CaptureContext()

    assert context.spectrum is None
    assert context.delay is None
    assert context.cycle_count is None
    assert context.waveform is None

    assert context.is_complete is False


def test_capture_context_is_complete_when_all_results_exist():
    context = CaptureContext(
        spectrum=SpectrumResult(
            frequencies_hz=[
                100e6,
                200e6,
            ],
            amplitudes_dbm=[
                -80.0,
                -70.0,
            ],
        ),
        delay=MeasurementResult(
            measurement="DELAY",
            value=1e-6,
            unit="s",
        ),
        cycle_count=MeasurementResult(
            measurement="CYCLE_COUNT",
            value=10.0,
            unit="count",
        ),
        waveform=WaveformResult(
            channel="CHANnel1",
            time_s=[
                0.0,
                1e-6,
            ],
            voltage_v=[
                0.1,
                0.2,
            ],
        ),
    )

    assert context.is_complete is True
