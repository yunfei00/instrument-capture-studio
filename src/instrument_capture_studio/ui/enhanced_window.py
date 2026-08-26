"""Phase 6/7 enhancements layered on top of the stable main window."""

from instrument_capture_studio.ui.main_window import MainWindow as BaseMainWindow


_STEP_LABELS = {
    "fsw_spectrum": "FSW Spectrum",
    "dsox_delay": "DSO-X DELAY",
    "dsox_cycle_count": "DSO-X CYCLE_COUNT",
    "dsox_waveform": "DSO-X Waveform",
    "save_result": "Save Result",
}


class MainWindow(BaseMainWindow):
    """Stable window with real step progress and reconnect feedback."""

    def __init__(self) -> None:
        super().__init__()
        self._controller.capture_progress.connect(self._on_capture_progress)
        self._controller.capture_recovery.connect(self._on_capture_recovery)
        self.statusBar().showMessage("就绪 · Phase 7")

    def _on_capture_progress(
        self,
        step_name: str,
        state: str,
        completed_steps: int,
        step_count: int,
    ) -> None:
        if step_count <= 0:
            return

        percent = int(round(completed_steps * 100 / step_count))
        percent = max(0, min(100, percent))
        label = _STEP_LABELS.get(step_name, step_name)

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(percent)

        if state == "running":
            self.progress_bar.setFormat(f"{percent}% · {label}")
            self._append_log(f"▶ {label}")
        elif state == "succeeded":
            self.progress_bar.setFormat(f"{percent}% · {label} 完成")
            self._append_log(f"✓ {label}")
        else:
            self.progress_bar.setFormat(f"{percent}% · {label} {state}")

    def _on_capture_recovery(
        self,
        next_attempt: int,
        max_attempts: int,
        error_type: str,
        message: str,
    ) -> None:
        self.job_state_label.setText("RECONNECTING")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat(
            f"自动重连 · {next_attempt}/{max_attempts}"
        )
        self._append_log(
            "↻ 自动重连："
            f"{error_type}: {message} "
            f"· 下一次尝试 {next_attempt}/{max_attempts}"
        )
        self.statusBar().showMessage(
            f"仪表通信中断，正在自动重连 · {next_attempt}/{max_attempts}"
        )
