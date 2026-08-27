from copy import deepcopy
from datetime import datetime, timezone

from instrument_capture_studio.app.combined_capture import (
    _begin_job_storage,
    _instrument_snapshot,
)
from instrument_capture_studio.core.models import CaptureResult, JobState
from instrument_capture_studio.workflows.paired import (
    PairedCaptureWorkflow,
    ProgressCallback,
)
from instrument_capture_studio.workflows.result_sink import (
    CaptureJobManifestSink,
    CaptureResultSink,
)


def run_connected_paired_capture(
    spectrum_analyzer,
    oscilloscope,
    *,
    job_id: str,
    fsw_timeout_s: float | None = None,
    cancel_check=None,
    result_sink: CaptureResultSink | None = None,
    job_manifest_sink: CaptureJobManifestSink | None = None,
    progress_callback: ProgressCallback | None = None,
    capture_metadata: dict[str, object] | None = None,
) -> CaptureResult:
    """Run one formal schema-v1 EXT+IMM paired sample on connected adapters."""
    result: CaptureResult | None = None
    application_started_at = datetime.now(timezone.utc)
    stage = "prepare_job_storage"
    stage_instrument = None

    try:
        _begin_job_storage(
            job_id,
            application_started_at,
            result_sink,
            job_manifest_sink,
        )
        stage = "snapshot_spectrum_analyzer"
        stage_instrument = spectrum_analyzer
        spectrum_snapshot = _instrument_snapshot(spectrum_analyzer)
        stage = "snapshot_oscilloscope"
        stage_instrument = oscilloscope
        oscilloscope_snapshot = _instrument_snapshot(oscilloscope)

        initial_metadata = deepcopy(capture_metadata or {})
        initial_metadata["recipe"] = "ext_imm_pair"
        initial_metadata["schema_version"] = 1
        initial_metadata["instruments"] = {
            "spectrum_analyzer": spectrum_snapshot,
            "oscilloscope": oscilloscope_snapshot,
        }

        stage = "workflow_run"
        stage_instrument = None
        workflow = PairedCaptureWorkflow(
            spectrum_analyzer=spectrum_analyzer,
            oscilloscope=oscilloscope,
            fsw_timeout_s=fsw_timeout_s,
            cancel_check=cancel_check,
            result_sink=result_sink,
            initial_metadata=initial_metadata,
            progress_callback=progress_callback,
        )
        result = workflow.run(job_id)
        return result
    except Exception as exc:
        if result is None:
            result = CaptureResult(
                job_id=job_id,
                state=JobState.FAILED,
                started_at=application_started_at,
                finished_at=datetime.now(timezone.utc),
                metadata={
                    **deepcopy(capture_metadata or {}),
                    "recipe": "ext_imm_pair",
                    "schema_version": 1,
                    "application_error": {
                        "stage": stage,
                        "instrument": (
                            None
                            if stage_instrument is None
                            else getattr(
                                stage_instrument,
                                "name",
                                type(stage_instrument).__name__,
                            )
                        ),
                        "address": (
                            None
                            if stage_instrument is None
                            else getattr(stage_instrument, "address", None)
                        ),
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    },
                },
            )
        raise
    finally:
        if result is not None and job_manifest_sink is not None:
            job_manifest_sink.save_job(result)


def run_paired_capture(
    spectrum_analyzer,
    oscilloscope,
    *,
    job_id: str,
    fsw_timeout_s: float | None = None,
    cancel_check=None,
    result_sink: CaptureResultSink | None = None,
    job_manifest_sink: CaptureJobManifestSink | None = None,
    progress_callback: ProgressCallback | None = None,
) -> CaptureResult:
    """Connect both instruments, run one paired sample, and always disconnect."""
    connected = []
    result: CaptureResult | None = None
    started_at = datetime.now(timezone.utc)
    try:
        _begin_job_storage(job_id, started_at, result_sink, job_manifest_sink)
        spectrum_analyzer.connect()
        connected.append(spectrum_analyzer)
        oscilloscope.connect()
        connected.append(oscilloscope)
        result = run_connected_paired_capture(
            spectrum_analyzer,
            oscilloscope,
            job_id=job_id,
            fsw_timeout_s=fsw_timeout_s,
            cancel_check=cancel_check,
            result_sink=result_sink,
            # Save manifest once, after disconnect metadata is known.
            job_manifest_sink=None,
            progress_callback=progress_callback,
        )
        return result
    except Exception as exc:
        if result is None:
            result = CaptureResult(
                job_id=job_id,
                state=JobState.FAILED,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata={
                    "recipe": "ext_imm_pair",
                    "schema_version": 1,
                    "application_error": {
                        "stage": "connect_or_capture",
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    },
                },
            )
        raise
    finally:
        disconnect_errors = []
        for adapter in reversed(connected):
            try:
                adapter.disconnect()
            except Exception as exc:
                disconnect_errors.append(
                    (adapter.name, type(exc).__name__, str(exc))
                )
        if result is not None and disconnect_errors:
            result.metadata["disconnect_errors"] = disconnect_errors
        if result is not None and job_manifest_sink is not None:
            job_manifest_sink.save_job(result)
