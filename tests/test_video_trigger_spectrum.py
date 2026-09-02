from datetime import datetime

import numpy as np
import pytest

from instrument_capture_studio.app.runtime import FSWRuntimeSettings
from instrument_capture_studio.core.models import JobState
from instrument_capture_studio.core.results import SpectrumResult, WaveformResult
from instrument_capture_studio.data.job_sink import JobDirectoryResultSink
from instrument_capture_studio.workflows.context import CaptureContext
from instrument_capture_studio.workflows.paired import PairedCaptureWorkflow


class FakeVideoFSW:
    video_trigger_enabled = True
    video_trigger_level_pct = 45.9

    def __init__(self, calls):
        self.calls = calls
        self.sweep_reads = 0

    def read_sweep_time_s(self):
        self.sweep_reads += 1
        value = 2e-5 if self.sweep_reads == 1 else 4e-5
        self.calls.append(("fsw", "sweep_time", value))
        return value

    def arm_external_current_setup(self):
        self.calls.append(("fsw", "arm_single", "EXT"))

    def read_armed_spectrum(self, **_kwargs):
        self.calls.append(("fsw", "read", "EXT"))
        return SpectrumResult(
            [700e6], [-50.0], {"trigger_source": "EXT", "acquisition_mode": "single"}
        )

    def acquire_freerun_current_setup(self, **_kwargs):
        self.calls.append(("fsw", "single", "IMM"))
        return SpectrumResult(
            [700e6], [-55.0], {"trigger_source": "IMM", "acquisition_mode": "single"}
        )

    def acquire_video_current_setup(self, *, sweep_time_s, **_kwargs):
        self.calls.append(("fsw", "single", "VID", sweep_time_s, -sweep_time_s / 2))
        return SpectrumResult(
            [700e6],
            [-48.0],
            {
                "trigger_source": "VID",
                "acquisition_mode": "single",
                "video_trigger": {
                    "enabled": True,
                    "sweep_time_s": sweep_time_s,
                    "video_level_pct_requested": 45.9,
                    "trigger_offset_s_requested": -sweep_time_s / 2,
                    "readback": {
                        "source": "VID",
                        "video_level_pct": 45.9,
                        "trigger_offset_s": -sweep_time_s / 2,
                        "slope": "POS",
                    },
                    "restore_errors": [],
                },
            },
        )


class FakeDSOX:
    def __init__(self, calls):
        self.calls = calls

    def configure_sync_window(self, sweep_time_s):
        self.calls.append(("dsox", "sync_config", sweep_time_s))
        return {
            "requested_position_s": sweep_time_s / 2,
            "requested_scale_s_per_div": sweep_time_s / 10,
        }

    def acquire_sync_waveform(self, **_kwargs):
        self.calls.append(("dsox", "single_sync"))
        return WaveformResult("CH1", [0.0], [0.1], 1e9, {"sample_kind": "sync"})

    def configure_followup_window(self):
        self.calls.append(("dsox", "followup_config"))
        return {
            "requested_position_s": 0.484,
            "requested_scale_s_per_div": 20e-9,
        }

    def acquire_followup_waveform(self, **_kwargs):
        self.calls.append(("dsox", "single_followup"))
        return WaveformResult(
            "CH1", [0.0], [0.2], 1e9, {"sample_kind": "followup"}
        )


class MemorySink:
    def __init__(self):
        self.context = None

    def save(self, job_id, context):
        self.context = context
        return ("spectrum_video.npz",)


def test_video_spectrum_is_appended_after_existing_four_acquisitions():
    calls = []
    sink = MemorySink()
    workflow = PairedCaptureWorkflow(
        FakeVideoFSW(calls),
        FakeDSOX(calls),
        fsw_timeout_s=5.0,
        result_sink=sink,
    )

    result = workflow.run("job-video")

    assert result.state is JobState.SUCCEEDED
    assert calls == [
        ("fsw", "sweep_time", 2e-5),
        ("dsox", "sync_config", 2e-5),
        ("fsw", "arm_single", "EXT"),
        ("dsox", "single_sync"),
        ("fsw", "read", "EXT"),
        ("dsox", "followup_config"),
        ("dsox", "single_followup"),
        ("fsw", "single", "IMM"),
        ("fsw", "sweep_time", 4e-5),
        ("fsw", "single", "VID", 4e-5, -2e-5),
    ]
    assert [step.name for step in result.steps][-3:] == [
        "fsw_video_sweep_time",
        "fsw_video_capture",
        "save_result",
    ]
    assert sink.context.is_paired_complete is True
    assert sink.context.spectrum_video is not None
    assert sink.context.metadata["fsw_video_trigger_offset_s_requested"] == -2e-5
    assert sink.context.metadata["fsw_video_trigger"]["video_level_pct_requested"] == 45.9


def test_video_runtime_settings_default_off_and_validate_level():
    settings = FSWRuntimeSettings(resource="MOCK::INSTR")
    assert settings.video_trigger_enabled is False
    assert settings.video_trigger_level_pct == 45.9

    with pytest.raises(ValueError, match="between 0 and 100"):
        FSWRuntimeSettings(
            resource="MOCK::INSTR",
            video_trigger_enabled=True,
            video_trigger_level_pct=100.1,
        )


def test_job_sink_persists_video_csv_npz_and_npz_metadata(tmp_path):
    context = CaptureContext(
        spectrum_ext=SpectrumResult([700e6], [-50.0], {}),
        spectrum_freerun=SpectrumResult([700e6], [-55.0], {}),
        spectrum_video=SpectrumResult(
            [700e6],
            [-48.0],
            {
                "trigger_source": "VID",
                "video_trigger": {
                    "sweep_time_s": 0.01,
                    "video_level_pct_requested": 45.9,
                    "trigger_offset_s_requested": -0.005,
                },
            },
        ),
        waveform_sync=WaveformResult("CH1", [0.0], [0.1], 1e9, {}),
        waveform_followup=WaveformResult("CH1", [0.0], [0.2], 1e9, {}),
        metadata={
            "recipe": "ext_imm_pair",
            "fsw_video_trigger": {
                "sweep_time_s": 0.01,
                "video_level_pct_requested": 45.9,
                "trigger_offset_s_requested": -0.005,
            },
        },
    )
    sink = JobDirectoryResultSink(
        tmp_path,
        clock=lambda: datetime(2026, 9, 2, 12, 0, 0),
    )

    files = sink.save("job-video", context)
    job_dir = tmp_path / "2026-09-02" / "job-video"

    assert str(job_dir / "spectrum_video.csv") in files
    assert str(job_dir / "spectrum_video.npz") in files
    assert (job_dir / "spectrum_video.csv").is_file()
    assert (job_dir / "spectrum_video.npz").is_file()

    with np.load(job_dir / "spectrum_video.npz", allow_pickle=False) as archive:
        keys = set(archive.files)
    assert "amplitude_dbm" in keys
