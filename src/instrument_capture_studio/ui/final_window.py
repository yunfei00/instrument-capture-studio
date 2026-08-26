"""Final Phase 7 desktop features before release hardening."""

from pathlib import Path

from PySide6.QtCore import QThread, Signal, Slot, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QSpinBox

from instrument_capture_studio.app.frequency_sweep import FrequencySweepPlan
from instrument_capture_studio.data.batch_trace_export import (
    BatchTraceExportResult,
    export_all_batch_traces,
)
from instrument_capture_studio.ui.product_window import MainWindow as ProductMainWindow


_CONTINUOUS_MODE = "固定频率连续采集"


class BatchTraceExportThread(QThread):
    """Keep large full-trace exports off the GUI thread."""

    progress = Signal(int, int, str)
    export_completed = Signal(object)
    export_failed = Signal(str, str)

    def __init__(self, manifest_path: Path, parent=None) -> None:
        super().__init__(parent)
        self._manifest_path = Path(manifest_path)

    def run(self) -> None:
        try:
            result = export_all_batch_traces(
                self._manifest_path,
                cancel_check=self.isInterruptionRequested,
                progress_callback=lambda completed, total, job_id: self.progress.emit(
                    completed,
                    total,
                    job_id,
                ),
            )
        except Exception as exc:
            self.export_failed.emit(type(exc).__name__, str(exc))
            return
        self.export_completed.emit(result)


class MainWindow(ProductMainWindow):
    """Product window with single, continuous, and frequency-sweep acquisition."""

    def __init__(self) -> None:
        self._continuous_running = False
        self._batch_export_thread: BatchTraceExportThread | None = None
        super().__init__()

        if self.capture_mode_combo.findText(_CONTINUOUS_MODE) < 0:
            self.capture_mode_combo.addItem(_CONTINUOUS_MODE)

        self._install_continuous_controls()
        self._install_full_export_action()

        # The parent restores preferences before the continuous controls exist.
        # Restore once more now that the full v1 control set is available.
        self._preferences.restore(self)
        self.repeat_capture_count_spin.valueChanged.connect(self._save_preferences)
        self.repeat_capture_count_spin.valueChanged.connect(self._update_sweep_summary)
        self.center_hz_edit.textChanged.connect(self._update_sweep_summary)
        self.span_hz_edit.textChanged.connect(self._update_sweep_summary)

        self._sync_sweep_mode()
        self._update_sweep_summary()
        self._update_result_actions()
        self.statusBar().showMessage("就绪 · Phase 7 Finalization")

    def _install_continuous_controls(self) -> None:
        group = self.start_button.parentWidget()
        layout = group.layout()

        self.repeat_capture_count_spin = QSpinBox(group)
        self.repeat_capture_count_spin.setObjectName("repeatCaptureCountSpin")
        self.repeat_capture_count_spin.setRange(1, 1_000_000)
        self.repeat_capture_count_spin.setValue(100)

        layout.addWidget(QLabel("固定频率连续次数"), 6, 0)
        layout.addWidget(self.repeat_capture_count_spin, 6, 1)
        note = QLabel("使用 FSW 中心频率/Span，Batch 内保持双仪表长连接")
        note.setObjectName("alphaNote")
        layout.addWidget(note, 6, 2, 1, 4)

    def _install_full_export_action(self) -> None:
        self.batch_trace_export_button = QPushButton("导出选中 Batch 全部曲线")
        self.batch_trace_export_button.setEnabled(False)

        toolbar = self.batch_report_button.parentWidget()
        toolbar_layout = toolbar.layout()
        toolbar_layout.insertWidget(1, self.batch_trace_export_button)
        self.batch_trace_export_button.clicked.connect(self._start_batch_trace_export)

    def _sync_sweep_mode(self, *_args) -> None:
        super()._sync_sweep_mode(*_args)
        mode = self.capture_mode_combo.currentIndex()
        continuous = mode == 2

        if hasattr(self, "repeat_capture_count_spin"):
            self.repeat_capture_count_spin.setEnabled(
                continuous and not self._capture_busy
            )

        if hasattr(self, "start_button"):
            if mode == 1:
                self.start_button.setText("开始频率循环采集")
            elif continuous:
                self.start_button.setText("开始固定频率连续采集")
            else:
                self.start_button.setText("开始采集")

    def _update_sweep_summary(self, *_args) -> None:
        if not hasattr(self, "capture_mode_combo"):
            return

        if self.capture_mode_combo.currentIndex() != 2:
            super()._update_sweep_summary(*_args)
            return

        if not hasattr(self, "repeat_capture_count_spin"):
            return

        try:
            center_hz = self._required_float(self.center_hz_edit, "中心频率")
            span_hz = self._required_float(self.span_hz_edit, "Span")
        except ValueError as exc:
            self.sweep_summary_label.setText(f"连续采集参数：{exc}")
            return

        self.sweep_summary_label.setText(
            f"固定 {center_hz / 1e6:g} MHz · "
            f"Span {span_hz / 1e6:g} MHz · "
            f"连续 {self.repeat_capture_count_spin.value()} 次联合采集 · "
            "Batch 内复用仪表长连接"
        )

    def _start_capture(self) -> None:
        mode = self.capture_mode_combo.currentIndex()
        if mode != 2:
            self._continuous_running = False
            super()._start_capture()
            return

        self._save_preferences()
        try:
            fsw_settings = self._build_fsw_settings()
            dsox_settings = self._build_dsox_settings()
            center_hz = self._required_float(self.center_hz_edit, "中心频率")
            span_hz = self._required_float(self.span_hz_edit, "Span")
            plan = FrequencySweepPlan(
                start_hz=center_hz,
                stop_hz=center_hz,
                step_hz=1.0,
                span_hz=span_hz,
                captures_per_frequency=self.repeat_capture_count_spin.value(),
            )
        except ValueError as exc:
            self._show_input_error(str(exc))
            return

        output_root = self.output_root_edit.text().strip()
        if not output_root:
            self._show_input_error("数据目录不能为空")
            return

        self._continuous_running = True
        self._sweep_running = True
        self._set_capture_busy(True)
        self.job_state_label.setText("CONTINUOUS STARTING")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("正在启动固定频率连续采集…")
        self._controller.start_frequency_sweep(
            fsw_settings,
            dsox_settings,
            output_root,
            plan,
        )

    def _on_batch_started(self, batch_id: str, total_captures: int) -> None:
        continuous = self._continuous_running
        super()._on_batch_started(batch_id, total_captures)
        if continuous:
            self.job_state_label.setText("CONTINUOUS RUNNING")
            self.statusBar().showMessage(
                f"固定频率连续采集中 · {batch_id} · 共 {total_captures} 次"
            )

    def _on_batch_progress(self, progress) -> None:
        super()._on_batch_progress(progress)
        if self._continuous_running and progress.state == "running":
            self.job_state_label.setText("CONTINUOUS RUNNING")
            self.statusBar().showMessage(
                f"固定 {progress.frequency_hz / 1e6:g} MHz · "
                f"采集 {progress.capture_index}/{progress.total_captures}"
            )

    def _on_batch_finished(self, result) -> None:
        continuous = self._continuous_running
        super()._on_batch_finished(result)
        self._continuous_running = False
        if continuous:
            self.statusBar().showMessage(
                f"固定频率连续采集结束 · {result.state.value.upper()} · "
                f"{result.completed_captures}/{result.total_captures}",
                10000,
            )

    def _set_capture_busy(self, busy: bool) -> None:
        super()._set_capture_busy(busy)
        if hasattr(self, "repeat_capture_count_spin"):
            self._sync_sweep_mode()
        if hasattr(self, "batch_trace_export_button"):
            self._update_result_actions()

    def _update_result_actions(self) -> None:
        super()._update_result_actions()
        if not hasattr(self, "batch_trace_export_button"):
            return
        export_running = (
            self._batch_export_thread is not None
            and self._batch_export_thread.isRunning()
        )
        self.batch_trace_export_button.setEnabled(
            not self._capture_busy
            and not export_running
            and self._selected_batch_manifest() is not None
        )

    @Slot()
    def _start_batch_trace_export(self) -> None:
        manifest_path = self._selected_batch_manifest()
        if manifest_path is None:
            QMessageBox.information(self, "全量曲线导出", "请先选择一个 Batch。")
            return
        if self._batch_export_thread is not None and self._batch_export_thread.isRunning():
            return

        thread = BatchTraceExportThread(manifest_path, self)
        self._batch_export_thread = thread
        thread.progress.connect(self._on_batch_trace_export_progress)
        thread.export_completed.connect(self._on_batch_trace_export_completed)
        thread.export_failed.connect(self._on_batch_trace_export_failed)
        thread.finished.connect(self._update_result_actions)

        self._append_log(f"开始导出 Batch 全部曲线：{manifest_path}")
        self.statusBar().showMessage("正在后台导出全部 Spectrum / Waveform 曲线…")
        self._update_result_actions()
        thread.start()

    @Slot(int, int, str)
    def _on_batch_trace_export_progress(
        self,
        completed: int,
        total: int,
        job_id: str,
    ) -> None:
        self.statusBar().showMessage(
            f"全量曲线导出 {completed}/{max(1, total)} · {job_id}"
        )

    @Slot(object)
    def _on_batch_trace_export_completed(
        self,
        result: BatchTraceExportResult,
    ) -> None:
        self._append_log(
            "Batch 全量曲线导出完成："
            f"{result.exported_files}/{result.total_files} · "
            f"失败 {result.failed_files} · {result.output_directory}"
        )
        if result.canceled:
            self.statusBar().showMessage("全量曲线导出已取消", 10000)
        else:
            self.statusBar().showMessage(
                f"全量曲线导出完成 · {result.exported_files} 张",
                10000,
            )
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(result.output_directory))
            )
        self._batch_export_thread = None
        self._update_result_actions()

    @Slot(str, str)
    def _on_batch_trace_export_failed(self, error_type: str, message: str) -> None:
        self._append_log(f"Batch 全量曲线导出失败：{error_type}: {message}")
        QMessageBox.warning(
            self,
            "全量曲线导出失败",
            f"{error_type}: {message}",
        )
        self.statusBar().showMessage("全量曲线导出失败", 10000)
        self._batch_export_thread = None
        self._update_result_actions()

    def closeEvent(self, event) -> None:
        if self._batch_export_thread is not None and self._batch_export_thread.isRunning():
            self._batch_export_thread.requestInterruption()
            self._batch_export_thread.wait(1500)
        super().closeEvent(event)
