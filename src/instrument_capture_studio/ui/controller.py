"""Qt background controller for instrument operations.

All VISA/driver work is executed on one worker thread. Cancellation uses a
threading.Event so a running FSW bounded poll can observe it immediately even
while the worker thread is busy inside the capture workflow.
"""

from pathlib import Path
from threading import Event
from uuid import uuid4

from PySide6.QtCore import QObject, QThread, Signal, Slot

from instrument_capture_studio.app.combined_capture import run_combined_capture
from instrument_capture_studio.app.runtime import (
    DSOXRuntimeSettings,
    FSWRuntimeSettings,
    build_dsox_adapter,
    build_fsw_adapter,
)
from instrument_capture_studio.data.job_sink import JobDirectoryResultSink


class HardwareWorker(QObject):
    log = Signal(str)
    instrument_tested = Signal(str, object)
    instrument_test_failed = Signal(str, str, str)
    capture_started = Signal(str)
    capture_progress = Signal(str, str, int, int)
    capture_finished = Signal(object)
    capture_failed = Signal(str, str)

    def __init__(self, cancel_event: Event) -> None:
        super().__init__()
        self._cancel_event = cancel_event

    @Slot(object)
    def test_fsw(self, settings: FSWRuntimeSettings) -> None:
        self._test_instrument("fsw", settings, build_fsw_adapter)

    @Slot(object)
    def test_dsox(self, settings: DSOXRuntimeSettings) -> None:
        self._test_instrument("dsox", settings, build_dsox_adapter)

    def _test_instrument(self, key, settings, factory) -> None:
        adapter = None
        try:
            self.log.emit(f"正在测试 {key.upper()} 连接…")
            adapter = factory(settings)
            adapter.connect()
            status = adapter.get_status()
            payload = {
                "name": status.name,
                "address": status.address,
                "model": status.model,
                "serial_number": status.serial_number,
                "firmware_version": status.firmware_version,
                "state": status.state.value,
            }
            self.instrument_tested.emit(key, payload)
            self.log.emit(
                f"{status.name} 连接测试成功：{status.model or 'unknown model'}"
            )
        except Exception as exc:
            self.instrument_test_failed.emit(
                key,
                type(exc).__name__,
                str(exc),
            )
            self.log.emit(
                f"{key.upper()} 连接测试失败：{type(exc).__name__}: {exc}"
            )
        finally:
            if adapter is not None:
                try:
                    adapter.disconnect()
                except Exception as exc:
                    self.log.emit(
                        f"{key.upper()} 测试断开失败：{type(exc).__name__}: {exc}"
                    )

    @Slot(object, object, str)
    def run_capture(
        self,
        fsw_settings: FSWRuntimeSettings,
        dsox_settings: DSOXRuntimeSettings,
        output_root: str,
    ) -> None:
        self._cancel_event.clear()
        job_id = f"capture-{uuid4().hex[:12]}"
        self.capture_started.emit(job_id)
        self.log.emit(f"开始联合采集：{job_id}")

        def report_progress(
            step_name: str,
            state: str,
            completed_steps: int,
            step_count: int,
        ) -> None:
            self.capture_progress.emit(
                step_name,
                state,
                completed_steps,
                step_count,
            )

        try:
            fsw = build_fsw_adapter(fsw_settings)
            dsox = build_dsox_adapter(dsox_settings)
            sink = JobDirectoryResultSink(
                Path(output_root).expanduser().resolve()
            )

            result = run_combined_capture(
                fsw,
                dsox,
                job_id=job_id,
                fsw_timeout_s=fsw_settings.step_timeout_s,
                cancel_check=self._cancel_event.is_set,
                result_sink=sink,
                job_manifest_sink=sink,
                progress_callback=report_progress,
            )
        except Exception as exc:
            self.capture_failed.emit(type(exc).__name__, str(exc))
            self.log.emit(f"采集异常：{type(exc).__name__}: {exc}")
            return

        self.capture_finished.emit(result)
        self.log.emit(f"采集结束：{job_id} · {result.state.value}")


class HardwareController(QObject):
    log = Signal(str)
    instrument_tested = Signal(str, object)
    instrument_test_failed = Signal(str, str, str)
    capture_started = Signal(str)
    capture_progress = Signal(str, str, int, int)
    capture_finished = Signal(object)
    capture_failed = Signal(str, str)

    _test_fsw_requested = Signal(object)
    _test_dsox_requested = Signal(object)
    _capture_requested = Signal(object, object, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cancel_event = Event()
        self._thread = QThread(self)
        self._worker = HardwareWorker(self._cancel_event)
        self._worker.moveToThread(self._thread)

        self._test_fsw_requested.connect(self._worker.test_fsw)
        self._test_dsox_requested.connect(self._worker.test_dsox)
        self._capture_requested.connect(self._worker.run_capture)

        self._worker.log.connect(self.log)
        self._worker.instrument_tested.connect(self.instrument_tested)
        self._worker.instrument_test_failed.connect(self.instrument_test_failed)
        self._worker.capture_started.connect(self.capture_started)
        self._worker.capture_progress.connect(self.capture_progress)
        self._worker.capture_finished.connect(self.capture_finished)
        self._worker.capture_failed.connect(self.capture_failed)

        self._thread.start()

    def test_fsw(self, settings: FSWRuntimeSettings) -> None:
        self._test_fsw_requested.emit(settings)

    def test_dsox(self, settings: DSOXRuntimeSettings) -> None:
        self._test_dsox_requested.emit(settings)

    def start_capture(
        self,
        fsw_settings: FSWRuntimeSettings,
        dsox_settings: DSOXRuntimeSettings,
        output_root: str,
    ) -> None:
        self._capture_requested.emit(
            fsw_settings,
            dsox_settings,
            output_root,
        )

    def cancel_capture(self) -> None:
        self._cancel_event.set()
        self.log.emit("已发送停止请求，等待当前仪表操作安全结束。")

    def shutdown(self, wait_ms: int = 1500) -> None:
        self._cancel_event.set()
        self._thread.quit()
        self._thread.wait(wait_ms)
