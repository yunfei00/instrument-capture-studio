"""Long-session frequency sweep / repeated formal Recipe capture runner."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from time import monotonic, sleep

from instrument_capture_studio.app.connected_capture import run_connected_capture
from instrument_capture_studio.app.frequency_sweep import FrequencySweepPlan
from instrument_capture_studio.app.recovery import (
    RecoveryPolicy,
    recovery_reason_from_exception,
    recovery_reason_from_result,
)
from instrument_capture_studio.core.models import CaptureResult, JobState
from instrument_capture_studio.data.batch_manifest import (
    build_batch_directory,
    load_batch_manifest,
    write_batch_manifest,
)
from instrument_capture_studio.data.custom_fields import normalize_user_fields
from instrument_capture_studio.data.job_sink import JobDirectoryResultSink


CancelCheck = Callable[[], bool]
PauseCheck = Callable[[], bool]
ProgressCallback = Callable[["BatchProgress"], None]
RecoveryCallback = Callable[[int, int, str, str], None]
PauseCallback = Callable[[bool, str, int, int], None]
LogCallback = Callable[[str], None]
CaptureRunner = Callable[..., CaptureResult]


class BatchState(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(frozen=True)
class BatchProgress:
    batch_id: str
    state: str
    frequency_hz: float
    frequency_index: int
    frequency_count: int
    capture_index: int
    captures_per_frequency: int
    completed_captures: int
    total_captures: int
    job_id: str


@dataclass(frozen=True)
class BatchCaptureResult:
    batch_id: str
    state: BatchState
    started_at: datetime
    finished_at: datetime
    manifest_path: str
    completed_captures: int
    failed_jobs: int
    total_captures: int
    last_error: str | None = None


def _emit_progress(
    callback: ProgressCallback | None,
    progress: BatchProgress,
) -> None:
    if callback is None:
        return
    try:
        callback(progress)
    except Exception:
        return


def _emit_pause(
    callback: PauseCallback | None,
    paused: bool,
    batch_id: str,
    completed: int,
    total: int,
) -> None:
    if callback is None:
        return
    try:
        callback(paused, batch_id, completed, total)
    except Exception:
        return


def _log(callback: LogCallback | None, message: str) -> None:
    if callback is None:
        return
    try:
        callback(message)
    except Exception:
        return


def _wait_with_cancel(
    delay_s: float,
    cancel_check: CancelCheck | None,
) -> bool:
    deadline = monotonic() + max(0.0, delay_s)
    while True:
        if cancel_check is not None and cancel_check():
            return False
        remaining = deadline - monotonic()
        if remaining <= 0:
            return True
        sleep(min(0.1, remaining))


def _open_session(fsw_factory, dsox_factory):
    fsw = fsw_factory()
    dsox = dsox_factory()
    connected = []
    try:
        fsw.connect()
        connected.append(fsw)
        dsox.connect()
        connected.append(dsox)
    except Exception:
        for adapter in reversed(connected):
            try:
                adapter.disconnect()
            except Exception:
                pass
        raise
    return fsw, dsox


def _close_session(fsw, dsox) -> None:
    for adapter in (dsox, fsw):
        if adapter is None:
            continue
        try:
            adapter.disconnect()
        except Exception:
            pass


def _first_result_error(result: CaptureResult) -> str | None:
    for step in result.steps:
        if step.error:
            return step.error
    application_error = result.metadata.get("application_error")
    if isinstance(application_error, dict):
        message = application_error.get("message")
        if message:
            return str(message)
    return None


def _parse_datetime(value: object, fallback: datetime) -> datetime:
    if not value:
        return fallback
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return fallback
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _successful_logical_keys(manifest: dict[str, object]) -> set[tuple[int, int]]:
    keys: set[tuple[int, int]] = set()
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        return keys
    for raw in jobs:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("state") or "").lower() != "succeeded":
            continue
        try:
            frequency_index = int(raw.get("frequency_index"))
            capture_index = int(raw.get("capture_index"))
        except (TypeError, ValueError):
            continue
        keys.add((frequency_index, capture_index))
    return keys


def _validate_resume_plan(
    manifest: dict[str, object],
    plan: FrequencySweepPlan,
) -> None:
    raw = manifest.get("plan")
    if not isinstance(raw, dict):
        raise ValueError("resumable batch is missing plan")
    expected = {
        "start_hz": plan.start_hz,
        "stop_hz": plan.stop_hz,
        "step_hz": plan.step_hz,
        "span_hz": plan.span_hz,
        "captures_per_frequency": plan.captures_per_frequency,
    }
    for key, expected_value in expected.items():
        try:
            actual = float(raw.get(key)) if key != "captures_per_frequency" else int(raw.get(key))
        except (TypeError, ValueError):
            raise ValueError(f"resumable batch has invalid plan field: {key}") from None
        if actual != expected_value:
            raise ValueError(
                f"resumable batch plan mismatch for {key}: {actual} != {expected_value}"
            )


def run_frequency_sweep_batch(
    *,
    fsw_factory,
    dsox_factory,
    plan: FrequencySweepPlan,
    batch_id: str,
    output_root: Path,
    fsw_timeout_s: float | None = None,
    cancel_check: CancelCheck | None = None,
    pause_check: PauseCheck | None = None,
    recovery_policy: RecoveryPolicy | None = None,
    progress_callback: ProgressCallback | None = None,
    recovery_callback: RecoveryCallback | None = None,
    pause_callback: PauseCallback | None = None,
    log_callback: LogCallback | None = None,
    capture_runner: CaptureRunner = run_connected_capture,
    resume_manifest_path: Path | None = None,
    user_fields: object = None,
) -> BatchCaptureResult:
    """Run or resume a full frequency sweep while reusing instrument sessions.

    Pause is cooperative and takes effect only at a complete logical-sample
    boundary. The current sample is allowed to finish, then both instrument
    sessions are released while PAUSED. Resume opens a fresh session and starts
    at the next unfinished logical sample.

    Project ``user_fields`` are frozen when a new Batch starts. Resume always
    reloads the frozen values from batch.json, so editing the GUI while a Batch
    is interrupted cannot change labels halfway through one dataset.
    """

    policy = recovery_policy or RecoveryPolicy()
    now = datetime.now(timezone.utc)
    output_root = Path(output_root)
    resume_sequence = 0
    requested_user_fields = normalize_user_fields(user_fields)

    if resume_manifest_path is not None:
        manifest_path = Path(resume_manifest_path).expanduser().resolve()
        manifest = load_batch_manifest(manifest_path)
        manifest_batch_id = str(manifest.get("batch_id") or "").strip()
        if not manifest_batch_id:
            raise ValueError("resumable batch is missing batch_id")
        if batch_id and batch_id != manifest_batch_id:
            raise ValueError("resume batch_id does not match manifest")
        batch_id = manifest_batch_id
        _validate_resume_plan(manifest, plan)
        frozen_user_fields = normalize_user_fields(manifest.get("user_fields"))
        started_at = _parse_datetime(manifest.get("started_at"), now)
        manifest.setdefault("jobs", [])
        manifest.setdefault("recovery_events", [])
        manifest.setdefault("resume_events", [])
        resume_sequence = int(manifest.get("resume_count") or 0) + 1
        previous_state = str(manifest.get("state") or "unknown")
        manifest["resume_count"] = resume_sequence
        manifest["resume_events"].append(
            {
                "time": now.isoformat(),
                "previous_state": previous_state,
                "completed_captures": len(_successful_logical_keys(manifest)),
            }
        )
        manifest["state"] = BatchState.RUNNING.value
        manifest["finished_at"] = None
        manifest["last_error"] = None
        write_batch_manifest(manifest_path, manifest)
        _log(
            log_callback,
            f"继续 Batch：{batch_id} · resume {resume_sequence} · "
            f"已完成 {len(_successful_logical_keys(manifest))}/{plan.total_captures}",
        )
    else:
        frozen_user_fields = requested_user_fields
        started_at = now
        batch_directory = build_batch_directory(output_root, batch_id, started_at)
        manifest_path = batch_directory / "batch.json"
        manifest = {
            "schema_version": 1,
            "batch_id": batch_id,
            "state": BatchState.RUNNING.value,
            "started_at": started_at.isoformat(),
            "finished_at": None,
            "user_fields": list(frozen_user_fields),
            "plan": {
                "start_hz": plan.start_hz,
                "stop_hz": plan.stop_hz,
                "step_hz": plan.step_hz,
                "span_hz": plan.span_hz,
                "captures_per_frequency": plan.captures_per_frequency,
                "frequency_count": plan.frequency_count,
                "total_captures": plan.total_captures,
                "frequencies_hz": list(plan.frequencies_hz),
            },
            "completed_captures": 0,
            "failed_jobs": 0,
            "jobs": [],
            "recovery_events": [],
            "resume_events": [],
            "resume_count": 0,
            "cursor": None,
            "last_error": None,
        }
        write_batch_manifest(manifest_path, manifest)

    sink = JobDirectoryResultSink(output_root)
    completed_keys = _successful_logical_keys(manifest)
    completed_captures = len(completed_keys)
    failed_jobs = int(manifest.get("failed_jobs") or 0)
    last_error = (
        str(manifest.get("last_error")) if manifest.get("last_error") else None
    )
    manifest["completed_captures"] = completed_captures

    fsw = None
    dsox = None

    def finish(state: BatchState, error: str | None = None) -> BatchCaptureResult:
        finished_at = datetime.now(timezone.utc)
        manifest["state"] = state.value
        manifest["finished_at"] = finished_at.isoformat()
        manifest["completed_captures"] = completed_captures
        manifest["failed_jobs"] = failed_jobs
        manifest["last_error"] = error
        manifest["resumable"] = (
            state in {BatchState.CANCELED, BatchState.FAILED}
            and completed_captures < plan.total_captures
        )
        write_batch_manifest(manifest_path, manifest)
        return BatchCaptureResult(
            batch_id=batch_id,
            state=state,
            started_at=started_at,
            finished_at=finished_at,
            manifest_path=str(manifest_path),
            completed_captures=completed_captures,
            failed_jobs=failed_jobs,
            total_captures=plan.total_captures,
            last_error=error,
        )

    try:
        for frequency_index, frequency_hz in enumerate(
            plan.frequencies_hz,
            start=1,
        ):
            for capture_index in range(1, plan.captures_per_frequency + 1):
                logical_key = (frequency_index, capture_index)
                if logical_key in completed_keys:
                    continue

                if pause_check is not None and pause_check():
                    _close_session(fsw, dsox)
                    fsw = None
                    dsox = None
                    manifest["state"] = BatchState.PAUSED.value
                    manifest["cursor"] = {
                        "frequency_index": frequency_index,
                        "capture_index": capture_index,
                        "frequency_hz": frequency_hz,
                    }
                    manifest["completed_captures"] = completed_captures
                    write_batch_manifest(manifest_path, manifest)
                    _emit_pause(
                        pause_callback,
                        True,
                        batch_id,
                        completed_captures,
                        plan.total_captures,
                    )
                    _log(
                        log_callback,
                        f"Batch 已暂停在逻辑样本边界：{completed_captures}/{plan.total_captures}",
                    )
                    while pause_check():
                        if cancel_check is not None and cancel_check():
                            return finish(
                                BatchState.CANCELED,
                                "batch canceled while paused",
                            )
                        sleep(0.1)
                    manifest["state"] = BatchState.RUNNING.value
                    manifest["cursor"] = {
                        "frequency_index": frequency_index,
                        "capture_index": capture_index,
                        "frequency_hz": frequency_hz,
                    }
                    write_batch_manifest(manifest_path, manifest)
                    _emit_pause(
                        pause_callback,
                        False,
                        batch_id,
                        completed_captures,
                        plan.total_captures,
                    )
                    _log(log_callback, "Batch 已继续，重新建立仪表会话。")

                attempt = 1

                while attempt <= policy.max_attempts:
                    if cancel_check is not None and cancel_check():
                        return finish(BatchState.CANCELED, "batch canceled by user")

                    base_job_id = (
                        f"{batch_id}-f{frequency_index:03d}"
                        f"-n{capture_index:04d}"
                    )
                    if resume_sequence:
                        base_job_id = f"{base_job_id}-resume{resume_sequence}"
                    job_id = (
                        base_job_id
                        if attempt == 1
                        else f"{base_job_id}-retry{attempt}"
                    )

                    manifest["cursor"] = {
                        "frequency_index": frequency_index,
                        "capture_index": capture_index,
                        "frequency_hz": frequency_hz,
                        "job_id": job_id,
                        "attempt": attempt,
                    }
                    write_batch_manifest(manifest_path, manifest)

                    if fsw is None or dsox is None:
                        try:
                            fsw, dsox = _open_session(fsw_factory, dsox_factory)
                            _log(
                                log_callback,
                                "已建立 FSW + DSO-X 长连接会话。",
                            )
                        except Exception as exc:
                            reason = recovery_reason_from_exception(exc)
                            last_error = f"{type(exc).__name__}: {exc}"
                            if reason is None or not policy.can_retry(attempt):
                                return finish(BatchState.FAILED, last_error)

                            next_attempt = attempt + 1
                            event = {
                                "time": datetime.now(timezone.utc).isoformat(),
                                "job_id": job_id,
                                "frequency_hz": frequency_hz,
                                "capture_index": capture_index,
                                "next_attempt": next_attempt,
                                "max_attempts": policy.max_attempts,
                                "error_type": reason.error_type,
                                "message": reason.message,
                                "stage": reason.stage,
                            }
                            manifest["recovery_events"].append(event)
                            write_batch_manifest(manifest_path, manifest)
                            if recovery_callback is not None:
                                recovery_callback(
                                    next_attempt,
                                    policy.max_attempts,
                                    reason.error_type,
                                    reason.message,
                                )
                            if not _wait_with_cancel(
                                policy.reconnect_delay_s,
                                cancel_check,
                            ):
                                return finish(
                                    BatchState.CANCELED,
                                    "batch canceled during reconnect wait",
                                )
                            attempt += 1
                            continue

                    frequency_config_started = monotonic()
                    fsw.configure_frequency(frequency_hz, plan.span_hz)
                    frequency_config_ms = (
                        monotonic() - frequency_config_started
                    ) * 1000.0

                    _emit_progress(
                        progress_callback,
                        BatchProgress(
                            batch_id=batch_id,
                            state="running",
                            frequency_hz=frequency_hz,
                            frequency_index=frequency_index,
                            frequency_count=plan.frequency_count,
                            capture_index=capture_index,
                            captures_per_frequency=plan.captures_per_frequency,
                            completed_captures=completed_captures,
                            total_captures=plan.total_captures,
                            job_id=job_id,
                        ),
                    )

                    try:
                        result = capture_runner(
                            fsw,
                            dsox,
                            job_id=job_id,
                            fsw_timeout_s=fsw_timeout_s,
                            cancel_check=cancel_check,
                            result_sink=sink,
                            job_manifest_sink=sink,
                            capture_metadata={
                                "user_fields": list(frozen_user_fields),
                                "batch": {
                                    "batch_id": batch_id,
                                    "frequency_hz": frequency_hz,
                                    "frequency_index": frequency_index,
                                    "frequency_count": plan.frequency_count,
                                    "capture_index": capture_index,
                                    "captures_per_frequency": (
                                        plan.captures_per_frequency
                                    ),
                                    "total_captures": plan.total_captures,
                                    "attempt": attempt,
                                    "resume_sequence": resume_sequence,
                                    "frequency_config_duration_ms": round(
                                        frequency_config_ms, 3
                                    ),
                                },
                            },
                        )
                    except Exception as exc:
                        reason = recovery_reason_from_exception(exc)
                        last_error = f"{type(exc).__name__}: {exc}"
                        _close_session(fsw, dsox)
                        fsw = None
                        dsox = None

                        if reason is None or not policy.can_retry(attempt):
                            return finish(BatchState.FAILED, last_error)

                        next_attempt = attempt + 1
                        manifest["recovery_events"].append(
                            {
                                "time": datetime.now(timezone.utc).isoformat(),
                                "job_id": job_id,
                                "frequency_hz": frequency_hz,
                                "capture_index": capture_index,
                                "next_attempt": next_attempt,
                                "max_attempts": policy.max_attempts,
                                "error_type": reason.error_type,
                                "message": reason.message,
                                "stage": reason.stage,
                            }
                        )
                        write_batch_manifest(manifest_path, manifest)
                        if recovery_callback is not None:
                            recovery_callback(
                                next_attempt,
                                policy.max_attempts,
                                reason.error_type,
                                reason.message,
                            )
                        if not _wait_with_cancel(
                            policy.reconnect_delay_s,
                            cancel_check,
                        ):
                            return finish(
                                BatchState.CANCELED,
                                "batch canceled during reconnect wait",
                            )
                        attempt += 1
                        continue

                    job_record = {
                        "job_id": result.job_id,
                        "state": result.state.value,
                        "frequency_hz": frequency_hz,
                        "frequency_index": frequency_index,
                        "capture_index": capture_index,
                        "attempt": attempt,
                        "resume_sequence": resume_sequence,
                        "frequency_config_duration_ms": round(
                            frequency_config_ms, 3
                        ),
                        "started_at": (
                            result.started_at.isoformat()
                            if result.started_at is not None
                            else None
                        ),
                        "finished_at": (
                            result.finished_at.isoformat()
                            if result.finished_at is not None
                            else None
                        ),
                        "output_files": list(result.output_files),
                        "error": _first_result_error(result),
                    }
                    manifest["jobs"].append(job_record)

                    if result.state is JobState.SUCCEEDED:
                        completed_keys.add(logical_key)
                        completed_captures = len(completed_keys)
                        manifest["completed_captures"] = completed_captures
                        manifest["cursor"] = None
                        write_batch_manifest(manifest_path, manifest)
                        _emit_progress(
                            progress_callback,
                            BatchProgress(
                                batch_id=batch_id,
                                state="succeeded",
                                frequency_hz=frequency_hz,
                                frequency_index=frequency_index,
                                frequency_count=plan.frequency_count,
                                capture_index=capture_index,
                                captures_per_frequency=(
                                    plan.captures_per_frequency
                                ),
                                completed_captures=completed_captures,
                                total_captures=plan.total_captures,
                                job_id=job_id,
                            ),
                        )
                        break

                    failed_jobs += 1
                    manifest["failed_jobs"] = failed_jobs
                    last_error = _first_result_error(result) or result.state.value
                    write_batch_manifest(manifest_path, manifest)
                    _emit_progress(
                        progress_callback,
                        BatchProgress(
                            batch_id=batch_id,
                            state=result.state.value,
                            frequency_hz=frequency_hz,
                            frequency_index=frequency_index,
                            frequency_count=plan.frequency_count,
                            capture_index=capture_index,
                            captures_per_frequency=plan.captures_per_frequency,
                            completed_captures=completed_captures,
                            total_captures=plan.total_captures,
                            job_id=job_id,
                        ),
                    )

                    if result.state is JobState.CANCELED:
                        return finish(BatchState.CANCELED, last_error)

                    reason = recovery_reason_from_result(result)
                    if reason is None or not policy.can_retry(attempt):
                        return finish(BatchState.FAILED, last_error)

                    _close_session(fsw, dsox)
                    fsw = None
                    dsox = None
                    next_attempt = attempt + 1
                    manifest["recovery_events"].append(
                        {
                            "time": datetime.now(timezone.utc).isoformat(),
                            "job_id": job_id,
                            "frequency_hz": frequency_hz,
                            "capture_index": capture_index,
                            "next_attempt": next_attempt,
                            "max_attempts": policy.max_attempts,
                            "error_type": reason.error_type,
                            "message": reason.message,
                            "stage": reason.stage,
                        }
                    )
                    write_batch_manifest(manifest_path, manifest)
                    if recovery_callback is not None:
                        recovery_callback(
                            next_attempt,
                            policy.max_attempts,
                            reason.error_type,
                            reason.message,
                        )
                    if not _wait_with_cancel(
                        policy.reconnect_delay_s,
                        cancel_check,
                    ):
                        return finish(
                            BatchState.CANCELED,
                            "batch canceled during reconnect wait",
                        )
                    attempt += 1

                else:
                    return finish(
                        BatchState.FAILED,
                        last_error or "maximum retry attempts exhausted",
                    )

        manifest["cursor"] = None
        return finish(BatchState.SUCCEEDED)

    finally:
        _close_session(fsw, dsox)
