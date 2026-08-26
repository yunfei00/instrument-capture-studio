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
from instrument_capture_studio.ui.enhanced_window import MainWindow as Phase7MainWindow
from instrument_capture_studio.ui.trace_viewer import (
    JsonViewerDialog,
    TraceViewerDialog,
)


class MainWindow(Phase7MainWindow):
    """Phase 7 product window with named templates and scalable result browsing."""

    def __init__(self) -> None:
        super().__init__()
        self._template_store = CaptureTemplateStore(default_template_directory())
        self._install_template_controls()
        self._refresh_template_list()
        self.data_tree.itemDoubleClicked.connect(self._open_data_item)
        self.data_tree.setToolTip(
            "双击 Job 打开目录；双击 NPZ 查看曲线；双击 JSON 查看详情。"
        )
        self._refresh_data_tree()
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
        self.template_load_button.setEnabled(bool(names))
        self.template_delete_button.setEnabled(bool(names))

    def _on_template_selected(self, name: str) -> None:
        if name and not self.template_name_edit.text().strip():
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

    def _refresh_data_tree(self) -> None:
        self.data_tree.clear()
        root = Path(self.output_root_edit.text()).expanduser()
        if not root.exists():
            self.data_tree.addTopLevelItem(QTreeWidgetItem(["暂无数据", str(root)]))
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

            for filename in (
                "job.json",
                "metadata.json",
                "spectrum.npz",
                "waveform.npz",
                "spectrum.csv",
                "waveform.csv",
            ):
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


def _file_description(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return f"{path.suffix.lstrip('.').upper() or 'FILE'} · {size} B"
