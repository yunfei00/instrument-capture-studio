from instrument_capture_studio.app.frequency_sweep import FrequencySweepPlan


def test_fixed_frequency_plan_reuses_batch_runner_model():
    plan = FrequencySweepPlan(
        start_hz=750e6,
        stop_hz=750e6,
        step_hz=1.0,
        span_hz=0.0,
        captures_per_frequency=100,
    )

    assert plan.frequencies_hz == (750e6,)
    assert plan.frequency_count == 1
    assert plan.total_captures == 100
