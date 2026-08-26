"""Phase 6/7 enhancements layered on top of the stable main window."""

from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from instrument_capture_studio.app.frequency_sweep import FrequencySweepPlan
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
    """Stable window with sweep capture, progress, reconnect, and persistence."""

    def __init__(self) -> None:
        super().__init__()
        self._sweep_running = False
        self._install_sweep_controls()

        self._preferences = WindowPreferences()
        self._preferences.restore(self)
        self._wire_preference_saves()
        self._sync_sweep_mode()
        self._update_sweep_summary()
        self._refresh_data_tree()

        self._controller.capture_progress.connect(self._on_capture_progress)
        self._controller.capture_recovery.connect(self._on_capture_recovery)
        self._controller.batch_started.connect(self._on_batch_started)
        self._controller.batch_progress.connect(self._on_batch_progress)
        self._controller.batch_finished.connect(self._on_batch_finished)
        self.statusBar().showMessage("就绪 · Phase 7")

    def _install_sweep_controls(self) -> None:
        group = self.start_button.parentWidget()
        layout = group.layout()
        if not isinstance(layout, QGridLayout):
            raise RuntimeError("capture group must use QGridLayout")

        self.capture_mode_combo = QComboBox()
        self.capture_mode_combo.setObjectName("captureModeCombo")
        self.capture_mode_combo.addItems(["单次采集", "频率循环采集"])

        self.sweep_start_mhz_edit = self._number_edit("700")
        self.sweep_start_mhz_edit.setObjectName("sweepStartMHzEdit")
        self.sweep_stop_mhz_edit = self._number_edit("800")
        self.sweep_stop_mhz_edit.setObjectName("sweepStopMHzEdit")
        self.sweep_step_mhz_edit = self._number_edit("5")
        self.sweep_step_mhz_edit.setObjectName("sweepStepMHzEdit")
        self.sweep_span_mhz_edit = self._number_edit("0")
        self.sweep_span_mhz_edit.setObjectName("sweepSpanMHzEdit")
        self.sweep_capture_count_spin = QSpinBox()
        self.sweep_capture_count_spin.setObjectName("sweepCaptureCountSpin")
        self.sweep_capture_count_spin.setRange(1, 1_000_000)
        self.sweep_capture_count_spin.setValue(1)

        sweep_widget = QWidget(group)
        sweep_grid = QGridLayout(sweep_widget)
        sweep_grid.setContentsMargins(0, 0, 0, 0)
        sweep_grid.setHorizontalSpacing(10)
        sweep_grid.addWidget(QLabel("起始频率 (MHz)"), 0, 0)
        sweep_grid.addWidget(self.sweep_start_mhz_edit, 0, 1)
        sweep_grid.addWidget(QLabel("结束频率 (MHz)"), 0, 2)
        sweep_grid.addWidget(self.sweep_stop_mhz_edit, 0, 3)
        sweep_grid.addWidget(QLabel("步长 (MHz)"), 0, 4)
        sweep_grid.addWidget(self.sweep_step_mhz_edit, 0, 5)
        sweep_grid.addWidget(QLabel("Span (MHz)"), 1, 0)
        sweep_grid.addWidget(self.sweep_span_mhz_edit, 1, 1)
        sweep_grid.addWidget(QLabel("每频点采集次数"), 1, 2)
        sweep_grid.addWidget(self.sweep_capture_count_spin, 1, 3)

        self.sweep_summary_label = QLabel("频率循环未启用")
        self.sweep_summary_label.setObjectName("alphaNote")
        self.sweep_summary_label.setWordWrap(True)
        sweep_grid.addWidget(self.sweep_summary_label, 1, 4, 1, 2)

        layout.addWidget(QLabel("采集模式"), 3, 0)
        layout.addWidget(self.capture_mode_combo, 3, 1, 1, 2)
        layout.addWidget(sweep_widget, 4, 0, 1, 6)

        self.capture_mode_combo.currentIndexChanged.connect(
            self._sync_sweep_mode
        )
        self.capture_mode_combo.currentIndexChanged.connect(
            self._update_sweep_summary
        )
        for edit in (
            self.sweep_start_mhz_edit,
            self.sweep_stop_mhz_edit,
            self.sweep_step_mhz_edit,
            self.sweep_span_mhz_edit,
        ):
            edit.textChanged.connect(self._update_sweep_summary)
        self.sweep_capture_count_spin.valueChanged.connect(
            self._update_sweep_summary
        )

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
            self.sweep_start_mhz_edit,
            self.sweep_stop_mhz_edit,
            self.sweep_step_mhz_edit,
            self.sweep_span_mhz_edit,
        )
        for widget in line_edits:
            widget.editingFinished.connect(self._save_preferences)

        combos = (
            self.trigger_source_combo,
            self.delay_edge1_combo,
            self.delay_edge2_combo,
            self.capture_mode_combo,
        )
        for widget in combos:
            widget.currentTextChanged.connect(self._save_preferences)

        self.waveform_channel_spin.valueChanged.connect(self._save_preferences)
        self.sweep_capture_count_spin.valueChanged.connect(self._save_preferences)

    def _save_preferences(self, *_args) -> None:
        self._preferences.save(self)

    def _sync_sweep_mode(self, *_args) -> None:
        enabled = self.capture_mode_combo.currentIndex() == 1
        usable = enabled and not self._capture_busy
        for widget in (
            self.sweep_start_mhz_edit,
            self.sweep_stop_mhz_edit,
            self.sweep_step_mhz_edit,
            self.sweep_span_mhz_edit,
            self.sweep_capture_count_spin,
        ):
            widget.setEnabled(usable)

        self.center_hz_edit.setEnabled(not enabled and not self._capture_busy)
        self.span_hz_edit.setEnabled(not enabled and not self._capture_busy)

    def _build_sweep_plan(self) -> FrequencySweepPlan:
        return FrequencySweepPlan(
            start_hz=self._required_float(
                self.sweep_start_mhz_edit,
                "起始频率",
            )
            * 1e6,
            stop_hz=self._required_float(
                self.sweep_stop_mhz_edit,
                "结束频率",
            )
            * 1e6,
            step_hz=self._required_float(
                self.sweep_step_mhz_edit,
                "频率步长",
            )
            * 1e6,
            span_hz=self._required_float(
                self.sweep_span_mhz_edit,
                "Span",
            )
            * 1e6,
            captures_per_frequency=self.sweep_capture_count_spin.value(),
        )

    def _update_sweep_summary(self, *_args) -> None:
        if self.capture_mode_combo.currentIndex() != 1:
            self.sweep_summary_label.setText("单次采集模式")
            return
        try:
            plan = self._build_sweep_plan()
        except ValueError as exc:
            self.sweep_summary_label.setText(f"频率循环参数：{exc}")
            return
        self.sweep_summary_label.setText(
            f"预计 {plan.frequency_count} 个频点 · "
            f"{plan.total_captures} 次联合采集 · "
            "Batch 内复用仪表长连接"
        )

    def _test_fsw_connection(self) -> None:
        self._save_preferences()
        super()._test_fsw_connection()

    def _test_dsox_connection(self) -> None:
        self._save_preferences()
        super()._test_dsox_connection()

    def _start_capture(self) -> None:
        self._save_preferences()
        if self.capture_mode_combo.currentIndex() == 0:
            self._sweep_running = False
            super()._start_capture()
            return

        try:
            fsw_settings = self._build_fsw_settings()
            dsox_settings = self._build_dsox_settings()
            plan = self._build_sweep_plan()
        except ValueError as exc:
            self._show_input_error(str(exc))
            return

        output_root = self.output_root_edit.text().strip()
        if not output_root:
            self._show_input_error("数据目录不能为空")
            return

        self._sweep_running = True
        self._set_capture_busy(True)
        self.job_state_label.setText("BATCH STARTING")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("正在启动频率循环采集…")
        self._controller.start_frequency_sweep(
            fsw_settings,
            dsox_settings,
            output_root,
            plan,
        )

    def _choose_output_root(self) -> None:
        super()._choose_output_root()
        self._save_preferences()

    def _set_capture_busy(self, busy: bool) -> None:
        super()._set_capture_busy(busy)
        if hasattr(self, "capture_mode_combo"):
            self.capture_mode_combo.setEnabled(not busy)
            self._sync_sweep_mode()

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
        if self._sweep_running:
            return
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
        if not self._sweep_running:
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

    def _on_batch_started(self, batch_id: str, total_captures: int) -> None:
        self._sweep_running = True
        self.job_state_label.setText("BATCH RUNNING")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"0/{total_captures} · {batch_id}")
        self._append_log(f"Batch ID：{batch_id}")
        self.statusBar().showMessage(f"频率循环采集中 · {batch_id}")

    def _on_batch_progress(self, progress) -> None:
        total = max(1, progress.total_captures)
        percent = int(round(progress.completed_captures * 100 / total))
        percent = max(0, min(100, percent))
        frequency_mhz = progress.frequency_hz / 1e6

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(
            f"{percent}% · {progress.completed_captures}/{progress.total_captures} · "
            f"{frequency_mhz:g} MHz · "
            f"{progress.capture_index}/{progress.captures_per_frequency}"
        )

        if progress.state == "running":
            self.job_state_label.setText("BATCH RUNNING")
            self.statusBar().showMessage(
                f"频点 {progress.frequency_index}/{progress.frequency_count} · "
                f"{frequency_mhz:g} MHz · "
                f"采集 {progress.capture_index}/{progress.captures_per_frequency}"
            )
        elif progress.state != "succeeded":
            self._append_log(
                f"Batch Job {progress.job_id} · {progress.state}"
            )

    def _on_batch_finished(self, result) -> None:
        self._sweep_running = False
        self._set_capture_busy(False)
        state = result.state.value.upper()
        self.job_state_label.setText(state)
        self.progress_bar.setRange(0, 100)
        percent = int(
            round(
                result.completed_captures
                * 100
                / max(1, result.total_captures)
            )
        )
        self.progress_bar.setValue(max(0, min(100, percent)))
        self.progress_bar.setFormat(
            f"{state} · {result.completed_captures}/{result.total_captures}"
        )
        self._append_log(f"Batch Manifest：{result.manifest_path}")
        if result.last_error:
            self._append_log(f"Batch 最后错误：{result.last_error}")
        self._refresh_data_tree()
        self.statusBar().showMessage(
            f"频率循环采集结束 · {state}",
            10000,
        )
