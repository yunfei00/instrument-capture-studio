"""Dedicated worker thread for the stateful recipe single-step debugger."""

from __future__ import annotations

from threading import Event

from PySide6.QtCore import QObject, QThread, Signal, Slot

from instrument_capture_studio.app.recipe_debug import RecipeDebugSession
from instrument_capture_studio.app.recipe_debug_runtime import (
    build_debug_dsox_driver,
    build_debug_fsw_driver,
)
from instrument_capture_studio.app.runtime import DSOXRuntimeSettings, FSWRuntimeSettings


class RecipeDebugWorker(QObject):
    log = Signal(str)
    session_started = Signal(object)
    step_finished = Signal(str, object)
    step_failed = Signal(str, str, str)
    session_reset = Signal(object)

    def __init__(self, cancel_event: Event) -> None:
        super().__init__()
        self._cancel_event = cancel_event
        self._session: RecipeDebugSession | None = None
        self._waveform_channel = 1

    @Slot(object, object)
    def start_session(
        self,
        fsw_settings: FSWRuntimeSettings,
        dsox_settings: DSOXRuntimeSettings,
    ) -> None:
        self._cancel_event.clear()
        if self._session is not None:
            self._reset_internal()
        self._waveform_channel = dsox_settings.waveform_channel
        try:
            self.log.emit("[DEBUG] 正在建立 FSW + DSO-X 调试会话…")
            session = RecipeDebugSession(
                build_debug_fsw_driver(fsw_settings),
                build_debug_dsox_driver(dsox_settings),
                fsw_timeout_s=fsw_settings.step_timeout_s,
                cancel_check=self._cancel_event.is_set,
            )
            payload = session.connect()
            self._session = session
        except Exception as exc:
            self.step_failed.emit("connect", type(exc).__name__, str(exc))
            self.log.emit(f"[DEBUG][FAIL] connect: {type(exc).__name__}: {exc}")
            return
        self.session_started.emit(payload)
        self.log.emit(
            "[DEBUG][PASS] 会话已连接："
            f"FSW={payload.get('fsw_model') or 'unknown'} · "
            f"DSO-X={payload.get('dsox_model') or 'unknown'}"
        )

    @Slot(str, object)
    def run_step(self, step_name: str, parameters: dict) -> None:
        session = self._session
        if session is None:
            self.step_failed.emit(step_name, "RuntimeError", "debug session is not connected")
            return
        try:
            if step_name == "read_sweep_time":
                payload = session.read_sweep_time()
            elif step_name == "configure_sync_scope":
                payload = session.configure_sync_scope()
            elif step_name == "arm_fsw_ext":
                payload = session.arm_fsw_ext()
            elif step_name == "capture_sync_scope":
                payload = session.capture_sync_scope(self._waveform_channel)
            elif step_name == "read_ext_spectrum":
                payload = session.read_ext_spectrum()
            elif step_name == "configure_followup_scope":
                payload = session.configure_followup_scope(
                    position_s=float(parameters["position_s"]),
                    scale_s_per_div=float(parameters["scale_s_per_div"]),
                )
            elif step_name == "capture_followup_scope":
                payload = session.capture_followup_scope(self._waveform_channel)
            elif step_name == "capture_freerun_spectrum":
                payload = session.capture_freerun_spectrum()
            else:
                raise ValueError(f"unknown debug step: {step_name}")
        except Exception as exc:
            self.step_failed.emit(step_name, type(exc).__name__, str(exc))
            self.log.emit(
                f"[DEBUG][FAIL] {step_name}: {type(exc).__name__}: {exc}"
            )
            return

        self.step_finished.emit(step_name, payload)
        self.log.emit(f"[DEBUG][PASS] {step_name} · state={payload.get('state')}")

    @Slot()
    def reset_session(self) -> None:
        payload = self._reset_internal()
        self.session_reset.emit(payload)

    def _reset_internal(self) -> dict[str, object]:
        self._cancel_event.set()
        session = self._session
        self._session = None
        if session is None:
            return {"state": "idle", "errors": []}
        try:
            payload = session.reset()
        except Exception as exc:
            payload = {
                "state": "closed",
                "errors": [f"{type(exc).__name__}: {exc}"],
            }
        self._cancel_event.clear()
        errors = payload.get("errors") or []
        if errors:
            self.log.emit("[DEBUG] 调试会话复位完成，但有清理告警：" + " | ".join(errors))
        else:
            self.log.emit("[DEBUG] 调试会话已复位：FSW ABORt → Free Run，DSO-X STOP，会话释放。")
        return payload


class RecipeDebugController(QObject):
    log = Signal(str)
    session_started = Signal(object)
    step_finished = Signal(str, object)
    step_failed = Signal(str, str, str)
    session_reset = Signal(object)

    _start_requested = Signal(object, object)
    _step_requested = Signal(str, object)
    _reset_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cancel_event = Event()
        self._thread = QThread(self)
        self._worker = RecipeDebugWorker(self._cancel_event)
        self._worker.moveToThread(self._thread)

        self._start_requested.connect(self._worker.start_session)
        self._step_requested.connect(self._worker.run_step)
        self._reset_requested.connect(self._worker.reset_session)
        self._worker.log.connect(self.log)
        self._worker.session_started.connect(self.session_started)
        self._worker.step_finished.connect(self.step_finished)
        self._worker.step_failed.connect(self.step_failed)
        self._worker.session_reset.connect(self.session_reset)
        self._thread.start()

    def start_session(
        self,
        fsw_settings: FSWRuntimeSettings,
        dsox_settings: DSOXRuntimeSettings,
    ) -> None:
        self._start_requested.emit(fsw_settings, dsox_settings)

    def run_step(self, step_name: str, parameters: dict | None = None) -> None:
        self._step_requested.emit(step_name, dict(parameters or {}))

    def reset_session(self) -> None:
        self._cancel_event.set()
        self._reset_requested.emit()

    def shutdown(self, wait_ms: int = 2000) -> None:
        self._cancel_event.set()
        self._thread.quit()
        self._thread.wait(wait_ms)
