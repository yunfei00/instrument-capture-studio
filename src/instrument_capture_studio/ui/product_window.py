"""Product-level desktop enhancements for templates and large result sets."""

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from instrument_capture_studio.data.capture_templates import (
    CaptureTemplateStore,
    default_template_directory,
)
from instrument_capture_studio.data.data_browser import (
    list_recent_batches,
    list_recent_jobs,
)
from instrument_capture_studio.data.session_log import (
    SessionLogWriter,
    default_session_log_directory,
)
from instrument_capture_studio.reporting.batch_report import export_batch_report
from instrument_capture_studio.ui.enhanced_window import MainWindow as Phase7MainWindow
from instrument_capture_studio.ui.trace_viewer import (
    JsonViewerDialog,
    TraceViewerDialog,
)


_FORMAL_JOB_FILES = (
    "job.json",
    "metadata.json",
    "spectrum_ext.npz",
    "waveform_sync.npz",
    "waveform_followup.npz",
    "spectrum_freerun.npz",
    "spectrum_imm.npz",
    "waveform_delay.npz",
    "waveform_cycle.npz",
    "spectrum_ext.csv",
    "waveform_sync.csv",
    "waveform_followup.csv",
    "spectrum_freerun.csv",
    "spectrum_imm.csv",
    "waveform_delay.csv",
    "waveform_cycle.csv",
)


class MainWindow(Phase7MainWindow):
    """Phase 7 product window with templates, browsing, plots, reports, and logs."""

    def __init__(self) -> None:
        super().__init__()
        self._session_log = SessionLogWriter(default_session_log_directory())
        self._template_store = CaptureTemplateStore(default_template_directory())
        self._install_template_controls()
        self._install_result_actions()
        self._refresh_template_list()
        self.data_tree.itemDoubleClicked.connect(self._open_data_item)
        self.data_tree.itemSelectionChanged.connect(self._update_result_actions)
        self.data_tree.setToolTip(
            "双击 Job 打开目录；双击 EXT/同步波形/第二次波形/Free Run NPZ 查看曲线；双击 JSON 查看详情。"
        )
        self._refresh_data_tree()
        self._append_log(f"会话日志：{self._session_log.path}")
        self.statusBar().showMessage("就绪 · Phase 7 Product")

    def _install_template_controls(self) -> None:
        group = self.start_button.parentWidget()
        layout = group.layout()
        if not isinstance(layout, QGridLayout):
            raise RuntimeError("capture group must use QGridLayout")

        self.template_combo = QComboBox()
        self.template_combo.setObjectName("captureTemplateCombo")
        self.template_name_edit = QLineEdit()
        self.template_name_edit.setObjectName("captureTemplateNameEdit")
        self.template_name_edit.setPlaceholderText("模板名称，例如 700-800MHz-100次")
        self.template_save_button = QPushButton("保存模板")
        self.template_load_button = QPushButton("加载模板")
        self.template_delete_button = QPushButton("删除")

        toolbar = QWidget(group)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.addWidget(self.template_combo, 2)
        toolbar_layout.addWidget(self.template_name_edit, 3)
        toolbar_layout.addWidget(self.template_save_button)
        toolbar_layout.addWidget(self.template_load_button)
        toolbar_layout.addWidget(self.template_delete_button)

        layout.addWidget(QLabel("实验配置模板"), 5, 0)
        layout.addWidget(toolbar, 5, 1, 1, 5)

        self.template_combo.currentTextChanged.connect(
            self._on_template_selected
        )
        self.template_save_button.clicked.connect(self._save_capture_template)
        self.template_load_button.clicked.connect(self._load_capture_template)
        self.template_delete_button.clicked.connect(self._delete_capture_template)

    def _install_result_actions(self) -> None:
        group = self.data_tree.parentWidget()
        layout = group.layout()
        toolbar = QWidget(group)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self.batch_report_button = QPushButton("生成选中 Batch HTML 报告")
        self.batch_report_button.setEnabled(False)
        self.open_session_log_button = QPushButton("打开本次会话日志")
        toolbar_layout.addWidget(self.batch_report_button)
        toolbar_layout.addWidget(self.open_session_log_button)
        toolbar_layout.addStretch(1)

        if isinstance(layout, QVBoxLayout):
            layout.insertWidget(1, toolbar)
        else:
            layout.addWidget(toolbar)

        self.batch_report_button.clicked.connect(self._generate_batch_report)
        self.open_session_log_button.clicked.connect(self._open_session_log)

    def _refresh_template_list(self, selected: str | None = None) -> None:
        names = self._template_store.list_names()
        current = selected or self.template_combo.currentText()
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_combo.addItems(list(names))
        if current:
            index = self.template_combo.findText(current)
            if index >= 0:
                self.template_combo.setCurrentIndex(index)
        self.template_combo.blockSignals(False)
        self.template_load_button.setEnabled(bool(names) and not self._capture_busy)

    def _on_template_selected(self, name: str) -> None:
        self.template_name_edit.setText(name)

    def _save_capture_template(self) -> None:
        name = self.template_name_edit.text().strip()
        try:
            record = self._template_store.save(
                name,
                self._preferences.snapshot(self),
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "保存模板失败",
                f"{type(exc).__name__}: {exc}",
            )
            return
        self._refresh_template_list(record.name)
        self._append_log(f"已保存实验配置模板：{record.name}")

    def _load_capture_template(self) -> None:
        name = self.template_combo.currentText().strip()
        if not name:
            return
        try:
            record = self._template_store.load(name)
            self._preferences.apply(self, record.values)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "加载模板失败",
                f"{type(exc).__name__}: {exc}",
            )
            return
        self._sync_sweep_mode()
        self._update_sweep_summary()
        self._append_log(f"已加载实验配置模板：{record.name}")

    def _delete_capture_template(self) -> None:
        name = self.template_combo.currentText().strip()
        if not name:
            return
        answer = QMessageBox.question(
            self,
            "删除模板",
            f"确认删除实验配置模板“{name}”？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._template_store.delete(name)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "删除模板失败",
                f"{type(exc).__name__}: {exc}",
            )
            return
        self._refresh_template_list()
        self._append_log(f"已删除实验配置模板：{name}")

    def _refresh_data_tree(self) -> None:
        self.data_tree.clear()
        root = self.output_root_edit.text().strip()
        if not root:
            return

        data_root = Path(root).expanduser()
        batches = list_recent_batches(data_root, limit=20)
        jobs = list_recent_jobs(data_root, limit=100)

        if batches:
            batch_root = QTreeWidgetItem(["Batches", "", ""])
            batch_root.setData(0, Qt.ItemDataRole.UserRole, ("group", "batches"))
            self.data_tree.addTopLevelItem(batch_root)
            for batch in batches:
                item = QTreeWidgetItem(
                    [
                        batch.batch_id,
                        batch.state.upper(),
                        (
                            f"{batch.completed_captures}/{batch.total_captures} · "
                            f"{batch.start_hz / 1e6:g}-{batch.stop_hz / 1e6:g} MHz"
                        ),
                    ]
                )
                item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    ("batch", str(batch.manifest_path)),
                )
                batch_root.addChild(item)
            batch_root.setExpanded(True)

        if jobs:
            job_root = QTreeWidgetItem(["Jobs", "", ""])
            job_root.setData(0, Qt.ItemDataRole.UserRole, ("group", "jobs"))
            self.data_tree.addTopLevelItem(job_root)
            for job in jobs:
                item = QTreeWidgetItem(
                    [
                        job.job_id,
                        job.state.upper(),
                        job.recipe or job.captured_at,
                    ]
                )
                item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    ("job", str(job.directory)),
                )
                job_root.addChild(item)
            job_root.setExpanded(True)

    def _open_data_item(self, item: QTreeWidgetItem, _column: int) -> None:
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not payload:
            return
        kind, raw_path = payload
        if kind == "job":
            QDesktopServices.openUrl(QUrl.fromLocalFile(raw_path))
            return
        if kind in {"batch", "group"}:
            return
        if kind == "file":
            path = Path(raw_path)
            if path.suffix.lower() == ".npz":
                dialog = TraceViewerDialog(path, self)
                dialog.exec()
            elif path.suffix.lower() == ".json":
                dialog = JsonViewerDialog(path, self)
                dialog.exec()

    def _update_result_actions(self) -> None:
        selected = self.data_tree.selectedItems()
        batch_selected = False
        if selected:
            payload = selected[0].data(0, Qt.ItemDataRole.UserRole)
            batch_selected = bool(payload and payload[0] == "batch")
        self.batch_report_button.setEnabled(batch_selected and not self._capture_busy)
        if hasattr(self, "batch_trace_export_button"):
            self.batch_trace_export_button.setEnabled(
                batch_selected and not self._capture_busy
            )

    def _selected_batch_manifest(self) -> Path | None:
        selected = self.data_tree.selectedItems()
        if not selected:
            return None
        payload = selected[0].data(0, Qt.ItemDataRole.UserRole)
        if not payload or payload[0] != "batch":
            return None
        return Path(payload[1])

    def _generate_batch_report(self) -> None:
        manifest = self._selected_batch_manifest()
        if manifest is None:
            return
        try:
            result = export_batch_report(manifest)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "生成 Batch 报告失败",
                f"{type(exc).__name__}: {exc}",
            )
            return
        self._append_log(
            f"Batch HTML 报告已生成：{result.report_html} · "
            f"timing={result.timing_csv}"
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.report_html)))

    def _open_session_log(self) -> None:
        self._session_log.flush()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._session_log.path)))

    def _append_log(self, message: str) -> None:
        super()._append_log(message)
        if hasattr(self, "_session_log"):
            self._session_log.write(message)

    def _set_capture_busy(self, busy: bool) -> None:
        super()._set_capture_busy(busy)
        if hasattr(self, "template_save_button"):
            self.template_save_button.setEnabled(not busy)
            self.template_load_button.setEnabled(
                bool(self.template_combo.count()) and not busy
            )
            self.template_delete_button.setEnabled(
                bool(self.template_combo.count()) and not busy
            )
        if hasattr(self, "batch_report_button"):
            self._update_result_actions()

    def closeEvent(self, event) -> None:
        if hasattr(self, "_session_log"):
            self._session_log.close()
        super().closeEvent(event)
