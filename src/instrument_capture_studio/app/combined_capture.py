from collections.abc import Callable
from datetime import datetime, timezone

from instrument_capture_studio.adapters.fsw_capture_settings import (
    read_fsw_frontend_snapshot,
)
from instrument_capture_studio.adapters.interfaces import (
    OscilloscopeAdapter,
    SpectrumAnalyzerAdapter,
)
from instrument_capture_studio.core.models import CaptureResult, JobState
from instrument_capture_studio.workflows.combined import (
    CombinedCaptureWorkflow,
    ProgressCallback,
)
from instrument_capture_studio.workflows.result_sink import (
    CaptureJobManifestSink,
    CaptureResultSink,
)


CancelCheck = Callable[[], bool]


def _can_read_fsw_frontend(adapter) -> bool:
    driver = getattr(adapter, "_driver", None)
    if driver is None:
        return False
    supports = getattr(driver, "supports", None)
    if callable(supports):
        return bool(supports("query"))
    return callable(getattr(driver, "query", None))


def _instrument_snapshot(adapter) -> dict[str, object]:
    """读取一次不可变的仪表身份和配置快照。"""

    status = adapter.get_status()
    snapshot: dict[str, object] = {
        "name": status.name,
        "address": status.address,
        "state": status.state.value,
        "model": status.model,
        "serial_number": status.serial_number,
        "firmware_version": status.firmware_version,
        "last_error": status.last_error,
        "configuration": dict(adapter.get_configuration()),
    }

    # FSW preamp and RF attenuation are measurement conditions, not product
    # settings. Query them before acquisition and keep them read-only. The helper
    # caches one snapshot per adapter/VISA session, so long Batch runs do not add
    # these queries to every logical sample. Lightweight test/legacy adapters
    # without a raw query capability keep the older snapshot contract.
    if (
        str(getattr(adapter, "name", "")).strip().upper() == "FSW"
        and _can_read_fsw_frontend(adapter)
    ):
        snapshot["frontend"] = read_fsw_frontend_snapshot(adapter)

    return snapshot


def _begin_job_storage(
    job_id: str,
    started_at: datetime,
    *sinks,
) -> None:
    """通知支持 Job 生命周期的 Sink 锁定任务目录。"""

    seen = set()
    for sink in sinks:
        if sink is None:
            continue

        identity = id(sink)
        if identity in seen:
            continue
        seen.add(identity)

        begin_job = getattr(sink, "begin_job", None)
        if callable(begin_job):
            begin_job(job_id, started_at)


def run_combined_capture(
    spectrum_analyzer: SpectrumAnalyzerAdapter,
    oscilloscope: OscilloscopeAdapter,
    *,
    job_id: str,
    fsw_timeout_s: float | None = None,
    cancel_check: CancelCheck | None = None,
    result_sink: CaptureResultSink | None = None,
    job_manifest_sink: CaptureJobManifestSink | None = None,
    progress_callback: ProgressCallback | None = None,
) -> CaptureResult:
    """
    连接两台仪表并执行一次完整联合采集。

    连接生命周期属于应用层：connect -> workflow -> disconnect。
    """

    connected = []
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

        stage = "connect_spectrum_analyzer"
        stage_instrument = spectrum_analyzer
        spectrum_analyzer.connect()
        connected.append(spectrum_analyzer)

        stage = "connect_oscilloscope"
        stage_instrument = oscilloscope
        oscilloscope.connect()
        connected.append(oscilloscope)

        stage = "snapshot_spectrum_analyzer"
        stage_instrument = spectrum_analyzer
        spectrum_snapshot = _instrument_snapshot(spectrum_analyzer)

        stage = "snapshot_oscilloscope"
        stage_instrument = oscilloscope
        oscilloscope_snapshot = _instrument_snapshot(oscilloscope)

        instrument_metadata = {
            "instruments": {
                "spectrum_analyzer": spectrum_snapshot,
                "oscilloscope": oscilloscope_snapshot,
            }
        }

        stage = "workflow_setup"
        stage_instrument = None
        workflow = CombinedCaptureWorkflow(
            spectrum_analyzer=spectrum_analyzer,
            oscilloscope=oscilloscope,
            fsw_timeout_s=fsw_timeout_s,
            cancel_check=cancel_check,
            result_sink=result_sink,
            initial_metadata=instrument_metadata,
            progress_callback=progress_callback,
        )

        stage = "workflow_run"
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
        disconnect_errors = []
        for adapter in reversed(connected):
            try:
                adapter.disconnect()
            except Exception as exc:
                disconnect_errors.append(
                    (
                        adapter.name,
                        type(exc).__name__,
                        str(exc),
                    )
                )

        if result is not None and disconnect_errors:
            result.metadata["disconnect_errors"] = disconnect_errors

        if result is not None and job_manifest_sink is not None:
            job_manifest_sink.save_job(result)
