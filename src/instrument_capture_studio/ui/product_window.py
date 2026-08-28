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
    # Standalone v1 recipe artifacts remain browseable.
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
            "双击 Job 打开目录；双击 EXT/同步/第二次/Free Run NPZ 查看曲线；双击 JSON 查看详情。"
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
        self.template_delete_button.setEnabled(bool(names) and not self._capture_busy)

    def _on_template_selected(self, name: str) -> None:
        if name:
            self.template_name_edit.setText(name)

    def _save_capture_template(self) -> None:
        name = self.template_name_edit.text().strip()
        if not name:
            name = self.template_combo.currentText().strip()
        try:
            record = self._template_store.save(
                name,
                self._preferences.snapshot(self),
            )
        except (OSError, ValueError) as exc:
            self._show_input_error(str(exc))
            return

        self.template_name_edit.setText(record.name)
        self._refresh_template_list(record.name)
        self._append_log(f"已保存配置模板：{record.name}")

    def _load_capture_template(self) -> None:
        name = self.template_combo.currentText().strip()
        if not name:
            self._show_input_error("请选择要加载的模板")
            return
        try:
            record = self._template_store.load(name)
        except (OSError, ValueError) as exc:
            self._show_input_error(str(exc))
            return

        self._preferences.apply(self, record.values)
        self._sync_sweep_mode()
        self._update_sweep_summary()
        self._save_preferences()
        self._refresh_data_tree()
        self.template_name_edit.setText(record.name)
        self._append_log(f"已加载配置模板：{record.name}")

    def _delete_capture_template(self) -> None:
        name = self.template_combo.currentText().strip()
        if not name:
            return
        answer = QMessageBox.question(
            self,
            "删除配置模板",
            f"确认删除模板“{name}”？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._template_store.delete(name)
        except OSError as exc:
            self._show_input_error(str(exc))
            return
        self.template_name_edit.clear()
        self._refresh_template_list()
        self._append_log(f"已删除配置模板：{name}")

    def _set_capture_busy(self, busy: bool) -> None:
        super()._set_capture_busy(busy)
        for attribute in (
            "template_combo",
            "template_name_edit",
            "template_save_button",
            "template_load_button",
            "template_delete_button",
            "batch_report_button",
        ):
            if hasattr(self, attribute):
                getattr(self, attribute).setEnabled(not busy)
        if hasattr(self, "_template_store") and not busy:
            self._refresh_template_list()
        if hasattr(self, "batch_report_button"):
            self._update_result_actions()

    def _refresh_data_tree(self) -> None:
        self.data_tree.clear()
        root = Path(self.output_root_edit.text()).expanduser()
        if not root.exists():
            self.data_tree.addTopLevelItem(QTreeWidgetItem(["暂无数据", str(root)]))
            if hasattr(self, "batch_report_button"):
                self._update_result_actions()
            return

        batches = list_recent_batches(root, limit=50)
        batch_root = QTreeWidgetItem(["批次结果", f"最近 {len(batches)} 个"])
        self.data_tree.addTopLevelItem(batch_root)
        for batch in batches:
            plan_parts = []
            if batch.start_hz is not None and batch.stop_hz is not None:
                plan_parts.append(
                    f"{batch.start_hz / 1e6:g}-{batch.stop_hz / 1e6:g} MHz"
                )
            if batch.step_hz is not None:
                plan_parts.append(f"step {batch.step_hz / 1e6:g} MHz")
            if batch.captures_per_frequency is not None:
                plan_parts.append(f"x{batch.captures_per_frequency}")
            summary = (
                f"{batch.state.upper()} · "
                f"{batch.completed_captures}/{batch.total_captures}"
            )
            if batch.failed_jobs:
                summary += f" · failed jobs {batch.failed_jobs}"
            if plan_parts:
                summary += " · " + " · ".join(plan_parts)

            node = QTreeWidgetItem([batch.batch_id, summary])
            node.setData(0, Qt.ItemDataRole.UserRole, str(batch.manifest_path))
            batch_root.addChild(node)

            directory_node = QTreeWidgetItem(["打开批次目录", str(batch.manifest_path.parent)])
            directory_node.setData(
                0,
                Qt.ItemDataRole.UserRole,
                str(batch.manifest_path.parent),
            )
            node.addChild(directory_node)

        jobs = list_recent_jobs(root, limit=100)
        job_root = QTreeWidgetItem(["最近 Job", f"最近 {len(jobs)} 个"])
        self.data_tree.addTopLevelItem(job_root)
        for job in jobs:
            try:
                relative = job.directory.relative_to(root)
            except ValueError:
                relative = job.directory
            node = QTreeWidgetItem(
                [job.job_id, f"{job.state.upper()} · {relative}"]
            )
            node.setData(0, Qt.ItemDataRole.UserRole, str(job.directory))
            job_root.addChild(node)

            for filename in _FORMAL_JOB_FILES:
                path = job.directory / filename
                if not path.exists():
                    continue
                child = QTreeWidgetItem([filename, _file_description(path)])
                child.setData(0, Qt.ItemDataRole.UserRole, str(path))
                node.addChild(child)

        batch_root.setExpanded(True)
        job_root.setExpanded(True)

        if not batches and not jobs:
            self.data_tree.addTopLevelItem(
                QTreeWidgetItem(["暂无可识别的 Batch / Job", str(root)])
            )
        if hasattr(self, "batch_report_button"):
            self._update_result_actions()

    def _selected_batch_manifest(self) -> Path | None:
        item = self.data_tree.currentItem()
        while item is not None:
            raw_path = item.data(0, Qt.ItemDataRole.UserRole)
            if raw_path:
                path = Path(str(raw_path))
                if path.is_file() and path.name == "batch.json":
                    return path
                if path.is_dir() and (path / "batch.json").exists():
                    return path / "batch.json"
            item = item.parent()
        return None

    def _update_result_actions(self) -> None:
        if not hasattr(self, "batch_report_button"):
            return
        enabled = (
            not self._capture_busy
            and self._selected_batch_manifest() is not None
        )
        self.batch_report_button.setEnabled(enabled)

    def _generate_batch_report(self) -> None:
        manifest_path = self._selected_batch_manifest()
        if manifest_path is None:
            QMessageBox.information(self, "Batch 报告", "请先选择一个 Batch。")
            return
        try:
            result = export_batch_report(manifest_path)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "生成报告失败",
                f"{type(exc).__name__}: {exc}",
            )
            self._append_log(f"生成 Batch 报告失败：{type(exc).__name__}: {exc}")
            return

        self._append_log(
            f"Batch HTML 报告：{result.report_html} · SVG {result.asset_count} 张"
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.report_html)))

    def _open_session_log(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._session_log.path)))

    def _open_data_item(self, item: QTreeWidgetItem, _column: int) -> None:
        raw_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not raw_path:
            return
        path = Path(str(raw_path))
        if not path.exists():
            QMessageBox.warning(self, "文件不存在", str(path))
            return

        try:
            if path.is_dir():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
                return
            if path.suffix.lower() == ".npz":
                TraceViewerDialog(path, self).exec()
                return
            if path.suffix.lower() == ".json":
                JsonViewerDialog(path, self).exec()
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except Exception as exc:
            QMessageBox.warning(
                self,
                "打开数据失败",
                f"{type(exc).__name__}: {exc}",
            )

    def _append_log(self, message: str) -> None:
        if hasattr(self, "_session_log"):
            try:
                self._session_log.append(message)
            except OSError:
                pass
        super()._append_log(message)

    def closeEvent(self, event) -> None:
        self._append_log("GUI 关闭请求")
        super().closeEvent(event)


def _file_description(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return f"{path.suffix.lstrip('.').upper() or 'FILE'} · {size} B"
