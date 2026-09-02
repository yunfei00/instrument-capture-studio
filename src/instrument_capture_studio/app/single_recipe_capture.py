from copy import deepcopy
from datetime import datetime, timezone

from instrument_capture_studio.app.combined_capture import (
    _begin_job_storage,
    _instrument_snapshot,
)
from instrument_capture_studio.core.models import CaptureResult, JobState
from instrument_capture_studio.workflows.result_sink import (
    CaptureJobManifestSink,
    CaptureResultSink,
)
from instrument_capture_studio.workflows.single_recipes import (
    DSOXOnlyWorkflow,
    ImmSpectrumOnlyWorkflow,
    ProgressCallback,
)


def _run_single_instrument(
    adapter,
    workflow_factory,
    *,
    recipe: str,
    instrument_key: str,
    job_id: str,
    result_sink: CaptureResultSink | None,
    job_manifest_sink: CaptureJobManifestSink | None,
    capture_metadata: dict[str, object] | None = None,
) -> CaptureResult:
    result: CaptureResult | None = None
    started_at = datetime.now(timezone.utc)
    connected = False
    try:
        _begin_job_storage(job_id, started_at, result_sink, job_manifest_sink)
        adapter.connect()
        connected = True
        metadata = deepcopy(capture_metadata or {})
        metadata.update(
            {
                "recipe": recipe,
                "instruments": {instrument_key: _instrument_snapshot(adapter)},
            }
        )
        result = workflow_factory(metadata).run(job_id)
        return result
    except Exception as exc:
        if result is None:
            result = CaptureResult(
                job_id=job_id,
                state=JobState.FAILED,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                metadata={
                    **deepcopy(capture_metadata or {}),
                    "recipe": recipe,
                    "application_error": {
                        "stage": "connect_or_capture",
                        "instrument": getattr(adapter, "name", type(adapter).__name__),
                        "address": getattr(adapter, "address", None),
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    },
                },
            )
        raise
    finally:
        if connected:
            try:
                adapter.disconnect()
            except Exception as exc:
                if result is not None:
                    result.metadata.setdefault("disconnect_errors", []).append(
                        (adapter.name, type(exc).__name__, str(exc))
                    )
        if result is not None and job_manifest_sink is not None:
            job_manifest_sink.save_job(result)


def run_imm_spectrum_capture(
    spectrum_analyzer,
    *,
    job_id: str,
    fsw_timeout_s: float | None = None,
    cancel_check=None,
    result_sink: CaptureResultSink | None = None,
    job_manifest_sink: CaptureJobManifestSink | None = None,
    progress_callback: ProgressCallback | None = None,
    capture_metadata: dict[str, object] | None = None,
) -> CaptureResult:
    return _run_single_instrument(
        spectrum_analyzer,
        lambda metadata: ImmSpectrumOnlyWorkflow(
            spectrum_analyzer,
            fsw_timeout_s=fsw_timeout_s,
            cancel_check=cancel_check,
            result_sink=result_sink,
            initial_metadata=deepcopy(metadata),
            progress_callback=progress_callback,
        ),
        recipe="imm_spectrum_only",
        instrument_key="spectrum_analyzer",
        job_id=job_id,
        result_sink=result_sink,
        job_manifest_sink=job_manifest_sink,
        capture_metadata=capture_metadata,
    )


def run_dsox_only_capture(
    oscilloscope,
    *,
    job_id: str,
    cancel_check=None,
    result_sink: CaptureResultSink | None = None,
    job_manifest_sink: CaptureJobManifestSink | None = None,
    progress_callback: ProgressCallback | None = None,
    capture_metadata: dict[str, object] | None = None,
) -> CaptureResult:
    return _run_single_instrument(
        oscilloscope,
        lambda metadata: DSOXOnlyWorkflow(
            oscilloscope,
            cancel_check=cancel_check,
            result_sink=result_sink,
            initial_metadata=deepcopy(metadata),
            progress_callback=progress_callback,
        ),
        recipe="dsox_only",
        instrument_key="oscilloscope",
        job_id=job_id,
        result_sink=result_sink,
        job_manifest_sink=job_manifest_sink,
        capture_metadata=capture_metadata,
    )
