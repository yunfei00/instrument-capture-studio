import json

from instrument_capture_studio.app.batch_configuration import (
    BatchCaptureConfiguration,
    batch_configuration_path,
    write_batch_configuration,
)
from instrument_capture_studio.app.capture_recipe import CaptureRecipe, ExecutionMode
from instrument_capture_studio.app.resume import (
    find_latest_resumable_batch,
    load_resumable_batch,
)
from instrument_capture_studio.app.runtime import DSOXRuntimeSettings, FSWRuntimeSettings


def _configuration():
    return BatchCaptureConfiguration(
        recipe=CaptureRecipe.EXT_IMM_PAIR,
        execution_mode=ExecutionMode.FIXED_REPEAT,
        fsw_settings=FSWRuntimeSettings(
            resource="TCPIP0::fsw::inst0::INSTR",
            step_timeout_s=30.0,
            center_frequency_hz=700e6,
            span_hz=0.0,
            rbw_hz=1e6,
            vbw_hz=1e6,
            trigger_source="EXT",
        ),
        dsox_settings=DSOXRuntimeSettings(
            resource="TCPIP0::scope::inst0::INSTR",
            waveform_channel=1,
            delay_timebase_scale_s=5e-7,
            cycle_timebase_scale_s=1e-4,
        ),
    )


def _write_manifest(
    root,
    batch_id,
    *,
    state,
    completed,
    captures=5,
    with_configuration=True,
):
    batch_dir = root / "batches" / "2026-08-27" / batch_id
    batch_dir.mkdir(parents=True)
    path = batch_dir / "batch.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "batch_id": batch_id,
                "state": state,
                "completed_captures": completed,
                "plan": {
                    "start_hz": 700e6,
                    "stop_hz": 700e6,
                    "step_hz": 1.0,
                    "span_hz": 0.0,
                    "captures_per_frequency": captures,
                    "total_captures": captures,
                },
            }
        ),
        encoding="utf-8",
    )
    if with_configuration:
        write_batch_configuration(
            batch_configuration_path(root, batch_id),
            _configuration(),
        )
    return path


def test_loads_canceled_batch_with_frozen_settings(tmp_path):
    path = _write_manifest(
        tmp_path,
        "batch-canceled",
        state="canceled",
        completed=2,
    )

    batch = load_resumable_batch(path)

    assert batch.batch_id == "batch-canceled"
    assert batch.completed_captures == 2
    assert batch.total_captures == 5
    assert batch.remaining_captures == 3
    assert batch.plan.start_hz == 700e6
    assert batch.configuration.execution_mode is ExecutionMode.FIXED_REPEAT
    assert batch.configuration.fsw_settings.resource.startswith("TCPIP0::fsw")
    assert batch.configuration.dsox_settings.waveform_channel == 1


def test_completed_batch_is_not_discovered(tmp_path):
    _write_manifest(
        tmp_path,
        "batch-done",
        state="succeeded",
        completed=5,
    )

    assert find_latest_resumable_batch(tmp_path) is None


def test_running_manifest_from_crash_is_discovered(tmp_path):
    _write_manifest(
        tmp_path,
        "batch-crashed",
        state="running",
        completed=1,
    )

    batch = find_latest_resumable_batch(tmp_path)

    assert batch is not None
    assert batch.batch_id == "batch-crashed"
    assert batch.state == "running"
    assert batch.remaining_captures == 4


def test_debug_batch_without_frozen_settings_is_not_offered_for_resume(tmp_path):
    _write_manifest(
        tmp_path,
        "batch-old-debug",
        state="canceled",
        completed=1,
        with_configuration=False,
    )

    assert find_latest_resumable_batch(tmp_path) is None
