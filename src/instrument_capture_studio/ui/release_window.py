"""Phase 8D release hardening for safe GUI shutdown.

The product must never destroy the VISA worker thread while an instrument call
is still running. A close request during capture or a connection test therefore
becomes a cooperative shutdown request: capture is canceled, the window stays
alive, and it closes automatically only after the active hardware operation has
reported completion.
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from instrument_capture_studio.ui.phase8_window import MainWindow as Phase8Window


class MainWindow(Phase8Window):
    """Release-hardened window with deferred close for hardware operations."""

    def __init__(self) -> None:
        self._close_after_hardware_idle = False
        self._connection_tests_active = 0
        super().__init__()
        self.statusBar().showMessage("就绪 · Phase 8D · Safe shutdown RC")

    def _test_fsw_connection(self) -> None:
        before = self.fsw_status_label.text()
        super()._test_fsw_connection()
        if self.fsw_status_label.text() == "测试中" and before != "测试中":
            self._connection_tests_active += 1

    def _test_dsox_connection(self) -> None:
        before = self.dsox_status_label.text()
        super()._test_dsox_connection()
        if self.dsox_status_label.text() == "测试中" and before != "测试中":
            self._connection_tests_active += 1

    def _on_instrument_tested(self, key: str, payload: dict) -> None:
        super()._on_instrument_tested(key, payload)
        self._finish_connection_test()

    def _on_instrument_test_failed(
        self,
        key: str,
        error_type: str,
        message: str,
    ) -> None:
        super()._on_instrument_test_failed(key, error_type, message)
        self._finish_connection_test()

    def _finish_connection_test(self) -> None:
        if self._connection_tests_active > 0:
            self._connection_tests_active -= 1
        self._schedule_close_if_hardware_idle()

    def _set_capture_busy(self, busy: bool) -> None:
        super()._set_capture_busy(busy)
        if not busy:
            self._schedule_close_if_hardware_idle()

    def _hardware_busy(self) -> bool:
        return self._capture_busy or self._connection_tests_active > 0

    def _schedule_close_if_hardware_idle(self) -> None:
        if self._close_after_hardware_idle and not self._hardware_busy():
            # Run close on the next GUI event-loop turn. This lets the queued
            # terminal signal handler return before QThread.quit()/wait().
            QTimer.singleShot(0, self.close)

    def closeEvent(self, event) -> None:
        if self._hardware_busy():
            first_request = not self._close_after_hardware_idle
            self._close_after_hardware_idle = True
            if self._capture_busy:
                self._controller.cancel_capture()
                self.job_state_label.setText("SAFE STOPPING")
                self.progress_bar.setFormat("关闭请求已接收 · 正在安全结束当前仪表操作…")
            self.statusBar().showMessage(
                "关闭请求已接收；等待当前仪表操作安全结束后自动退出。"
            )
            if first_request:
                QMessageBox.information(
                    self,
                    "正在安全退出",
                    "当前仍有仪表操作。程序不会强制终止 VISA 线程；"
                    "将先安全结束当前操作并释放仪表，然后自动关闭。",
                )
            event.ignore()
            return

        self._close_after_hardware_idle = False
        super().closeEvent(event)
