import pytest

from instrument_capture_studio.app.frequency_sweep import FrequencySweepPlan


def test_frequency_sweep_includes_700_to_800_mhz_by_5_mhz():
    plan = FrequencySweepPlan(
        start_hz=700e6,
        stop_hz=800e6,
        step_hz=5e6,
        span_hz=0,
        captures_per_frequency=3,
    )

    assert plan.frequency_count == 21
    assert plan.frequencies_hz[0] == 700e6
    assert plan.frequencies_hz[-1] == 800e6
    assert plan.total_captures == 63
    assert plan.span_hz == 0


def test_frequency_sweep_stops_before_unreachable_stop_value():
    plan = FrequencySweepPlan(
        start_hz=700e6,
        stop_hz=712e6,
        step_hz=5e6,
        span_hz=1e6,
        captures_per_frequency=1,
    )

    assert plan.frequencies_hz == (700e6, 705e6, 710e6)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start_hz": -1},
        {"start_hz": 800, "stop_hz": 700},
        {"step_hz": 0},
        {"span_hz": -1},
        {"captures_per_frequency": 0},
    ],
)
def test_frequency_sweep_rejects_invalid_plan(kwargs):
    values = {
        "start_hz": 700,
        "stop_hz": 800,
        "step_hz": 5,
        "span_hz": 0,
        "captures_per_frequency": 1,
    }
    values.update(kwargs)

    with pytest.raises(ValueError):
        FrequencySweepPlan(**values)
