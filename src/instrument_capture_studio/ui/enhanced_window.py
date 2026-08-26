"""Phase 6/7 enhancements layered on top of the stable main window."""

from instrument_capture_studio.ui.main_window import MainWindow as BaseMainWindow
from instrument_capture_studio.ui.preferences import WindowPreferences


_STEP_LABELS = {
    "fsw_spectrum": "FSW Spectrum",
    "dsox_delay": "DSO-X DELAY",
    "dsox_cycle_count": "DSO-X CYCLE_COUNT",
    "dsox_waveform": "DSO-X Waveform",
    "save_result": "Save Result",
}


class MainWindow(BaseMainWindow):
    """Stable window with progress, reconnect feedback, and saved parameters."""

    def __init__(self) -> None:
        super().__init__()
        self._preferences = WindowPreferences()
        self._preferences.restore(self)
        self._wire_preference_saves()
        self._refresh_data_tree()

        self._controller.capture_progress.connect(self._on_capture_progress)
        self._controller.capture_recovery.connect(self._on_capture_recovery)
        self.statusBar().showMessage("就绪 · Phase 7")

    def _wire_preference_saves(self) -> None:
        line_edits = (
            self.fsw_resource_edit,
            self.center_hz_edit,
            self.span_hz_edit,
            self.rbw_hz_edit,
            self.vbw_hz_edit,
            self.fsw_timeout_edit,
            self.dsox_resource_edit,
            self.delay_source1_edit,
            self.delay_source2_edit,
            self.cycle_source_edit,
            self.output_root_edit,
        )
        for widget in line_edits:
            widget.editingFinished.connect(self._save_preferences)

        combos = (
            self.trigger_source_combo,
            self.delay_edge1_combo,
            self.delay_edge2_combo,
        )
        for widget in combos:
            widget.currentTextChanged.connect(self._save_preferences)

        self.waveform_channel_spin.valueChanged.connect(self._save_preferences)

    def _save_preferences(self, *_args) -> None:
        self._preferences.save(self)

    def _test_fsw_connection(self) -> None:
        self._save_preferences()
        super()._test_fsw_connection()

    def _test_dsox_connection(self) -> None:
        self._save_preferences()
        super()._test_dsox_connection()

    def _start_capture(self) -> None:
        self._save_preferences()
        super()._start_capture()

    def _choose_output_root(self) -> None:
        super()._choose_output_root()
        self._save_preferences()

    def closeEvent(self, event) -> None:
        self._save_preferences()
        super().closeEvent(event)

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
