from instrument_capture_studio.app.batch_configuration import (
    BatchCaptureConfiguration,
    batch_configuration_path,
    configuration_path_for_manifest,
    load_batch_configuration,
    write_batch_configuration,
)
from instrument_capture_studio.app.capture_recipe import CaptureRecipe, ExecutionMode
from instrument_capture_studio.app.runtime import DSOXRuntimeSettings, FSWRuntimeSettings


def _configuration():
    return BatchCaptureConfiguration(
        recipe=CaptureRecipe.EXT_IMM_PAIR,
        execution_mode=ExecutionMode.FREQUENCY_SWEEP,
        fsw_settings=FSWRuntimeSettings(
            resource="TCPIP0::fsw::inst0::INSTR",
            transport_timeout_ms=17000,
            step_timeout_s=31.0,
            center_frequency_hz=700e6,
            span_hz=0.0,
            rbw_hz=1e6,
            vbw_hz=2e6,
            trigger_source="EXT",
        ),
        dsox_settings=DSOXRuntimeSettings(
            resource="TCPIP0::scope::inst0::INSTR",
            transport_timeout_ms=12000,
            single_timeout_s=37.0,
            delay_source1="CHANnel1",
            delay_source2="CHANnel2",
            delay_edge1="+1",
            delay_edge2="-1",
            cycle_count_source="CHANnel1",
            waveform_channel=1,
            delay_timebase_scale_s=5e-7,
            cycle_timebase_scale_s=1e-4,
            followup_position_s=0.484,
            followup_scale_s=20e-9,
        ),
    )


def test_frozen_batch_configuration_roundtrip(tmp_path):
    configuration = _configuration()
    path = batch_configuration_path(tmp_path, "batch-demo")

    write_batch_configuration(path, configuration)
    loaded = load_batch_configuration(path)

    assert loaded == configuration
    assert loaded.fsw_settings.transport_timeout_ms == 17000
    assert loaded.dsox_settings.waveform_channel == 1
    assert loaded.dsox_settings.delay_edge2 == "-1"
    assert loaded.dsox_settings.single_timeout_s == 37.0
    assert loaded.dsox_settings.followup_position_s == 0.484
    assert loaded.dsox_settings.followup_scale_s == 20e-9


def test_configuration_path_is_derived_from_batch_manifest(tmp_path):
    manifest = (
        tmp_path
        / "batches"
        / "2026-08-27"
        / "batch-demo"
        / "batch.json"
    )
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")

    assert configuration_path_for_manifest(manifest) == (
        tmp_path / "batch-configs" / "batch-demo.json"
    )
