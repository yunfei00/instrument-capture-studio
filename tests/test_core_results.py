from instrument_capture_studio.core.results import (
    MeasurementResult,
    SpectrumResult,
    WaveformResult,
)


def test_measurement_result():
    result = MeasurementResult(
        measurement="DELAY",
        value=1.23e-6,
        unit="s",
    )

    assert result.measurement == "DELAY"
    assert result.value == 1.23e-6
    assert result.unit == "s"


def test_waveform_points():
    result = WaveformResult(
        channel="CH1",
        time_s=[0.0, 1e-6, 2e-6],
        voltage_v=[0.1, 0.2, 0.3],
    )

    assert result.points == 3


def test_spectrum_points():
    result = SpectrumResult(
        frequencies_hz=[
            600e6,
            605e6,
            610e6,
        ],
        amplitudes_dbm=[
            -50.0,
            -48.0,
            -51.0,
        ],
    )

    assert result.points == 3
