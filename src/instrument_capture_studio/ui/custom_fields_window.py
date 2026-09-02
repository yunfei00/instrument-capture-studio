"""Project-record UI layered on top of the portable review workspace."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from instrument_capture_studio.data.batch_manifest import load_batch_manifest
from instrument_capture_studio.data.custom_fields import (
    MAX_CUSTOM_FIELDS,
    normalize_user_fields,
    read_sample_user_fields,
    update_batch_user_fields,
    update_directory_user_fields,
    write_sample_user_fields,
)
from instrument_capture_studio.ui.large_data_window import _KIND_ROLE
from instrument_capture_studio.ui.review_window import MainWindow as ReviewWindow


_EXAMPLE_NAMES = (
    "项目名称",
    "测试场景",
    "手机型号",
    "Android版本",
    "软件版本",
    "样机编号",
    "测试地点",
    "测试人员",
    "环境条件",
    "备注",
)


class CustomFieldsDialog(QDialog):
    """Edit exactly ten optional name/value rows while preserving row order."""

    def __init__(self, fields=(), *, title="项目记录 / 自定义字段", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(720)
        self._name_edits: list[QLineEdit] = []
        self._value_edits: list[QLineEdit] = []
        self._build_ui(fields)

    def _build_ui(self, fields) -> None:
        root = QVBoxLayout(self)
        hint = QLabel(
            "最多 10 项。名称和值均可手工输入；空白行不会保存。名称不能重复。"
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(7)
        grid.addWidget(QLabel("序号"), 0, 0)
        grid.addWidget(QLabel("名称"), 0, 1)
        grid.addWidget(QLabel("值"), 0, 2)

        normalized = list(normalize_user_fields(fields))
        for index in range(MAX_CUSTOM_FIELDS):
            name_edit = QLineEdit(self)
            value_edit = QLineEdit(self)
            name_edit.setObjectName(f"customFieldName{index + 1}")
            value_edit.setObjectName(f"customFieldValue{index + 1}")
            name_edit.setPlaceholderText(_EXAMPLE_NAMES[index])
            value_edit.setPlaceholderText("输入值")
            if index < len(normalized):
                name_edit.setText(normalized[index]["name"])
                value_edit.setText(normalized[index]["value"])
            self._name_edits.append(name_edit)
            self._value_edits.append(value_edit)
            grid.addWidget(QLabel(str(index + 1)), index + 1, 0)
            grid.addWidget(name_edit, index + 1, 1)
            grid.addWidget(value_edit, index + 1, 2)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 2)
        root.addLayout(grid)

        actions = QHBoxLayout()
        clear_button = QPushButton("清空全部", self)
        clear_button.clicked.connect(self._clear_all)
        actions.addWidget(clear_button)
        actions.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        root.addLayout(actions)

    def _clear_all(self) -> None:
        for edit in (*self._name_edits, *self._value_edits):
            edit.clear()

    def fields(self) -> tuple[dict[str, str], ...]:
        return normalize_user_fields(
            [
                {"name": name.text(), "value": value.text()}
                for name, value in zip(self._name_edits, self._value_edits)
            ]
        )

    def _accept_if_valid(self) -> None:
        try:
            self.fields()
        except ValueError as exc:
            QMessageBox.warning(self, "项目记录", str(exc))
            return
        self.accept()


class MainWindow(ReviewWindow):
    """v1.2 workspace with capture-time and post-capture project records."""

    def __init__(self) -> None:
        self._project_user_fields: tuple[dict[str, str], ...] = ()
        super().__init__()
        self._install_project_record_controls()
        self._install_record_request_injection()
        self._refresh_project_record_summary()
        self.statusBar().showMessage("就绪 · v1.2.0 · 项目记录")

    # ------------------------------------------------------------------
    # Capture-time project records
    # ------------------------------------------------------------------
    def _install_project_record_controls(self) -> None:
        card = self.commercial_task_parameter_card
        grid = card.layout() if card is not None else None
        if not isinstance(grid, QGridLayout):
            raise RuntimeError("task parameter card must use QGridLayout")

        row = grid.rowCount()
        self.project_record_button = QPushButton("编辑 10 项…", card)
        self.project_record_button.setObjectName("projectRecordButton")
        self.project_record_button.setToolTip(
            "采集开始时冻结到 Batch，并随每个样本保存为 sample_info.json。"
        )
        self.project_record_summary = QLabel("未填写项目记录", card)
        self.project_record_summary.setObjectName("projectRecordSummary")
        self.project_record_summary.setWordWrap(True)
        grid.addWidget(QLabel("项目记录", card), row, 0)
        grid.addWidget(self.project_record_button, row, 1)
        grid.addWidget(self.project_record_summary, row, 2, 1, 2)
        self.project_record_button.clicked.connect(self._edit_capture_project_records)

        bar = self.findChild(QWidget, "largeDataFilterBar")
        layout = bar.layout() if bar is not None else None
        self.edit_data_records_button = QPushButton("编辑项目记录", bar or self)
        self.edit_data_records_button.setObjectName("editDataRecordsButton")
        self.edit_data_records_button.setToolTip(
            "修改当前 Batch、频率目录或单个样本的 sample_info.json。"
        )
        self.directory_records_button = QPushButton("目录项目记录", bar or self)
        self.directory_records_button.setObjectName("directoryRecordsButton")
        self.directory_records_button.setToolTip(
            "选择任意已复制的数据根目录，批量创建或修改 sample_info.json。"
        )
        if layout is not None:
            layout.addWidget(self.edit_data_records_button)
            layout.addWidget(self.directory_records_button)
        self.edit_data_records_button.clicked.connect(self._edit_selected_data_records)
        self.directory_records_button.clicked.connect(self._edit_arbitrary_directory_records)
        self.data_tree.itemSelectionChanged.connect(self._refresh_record_actions)
        self._refresh_record_actions()

    def _install_record_request_injection(self) -> None:
        # Keep acquisition orchestration untouched: enrich the request immediately
        # before it enters the existing HardwareController. Batch resume ignores
        # this GUI value and reloads its frozen fields from batch.json in backend.
        self._start_recipe_without_project_fields = self._controller.start_recipe
        self._controller.start_recipe = self._start_recipe_with_project_fields

    def _start_recipe_with_project_fields(self, request: dict) -> None:
        enriched = dict(request)
        enriched["user_fields"] = [dict(item) for item in self._project_user_fields]
        self._start_recipe_without_project_fields(enriched)

    def _edit_capture_project_records(self) -> None:
        if self._capture_busy:
            return
        dialog = CustomFieldsDialog(self._project_user_fields, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._project_user_fields = dialog.fields()
        self._refresh_project_record_summary()

    def _refresh_project_record_summary(self) -> None:
        if not hasattr(self, "project_record_summary"):
            return
        fields = self._project_user_fields
        if not fields:
            self.project_record_summary.setText("未填写项目记录 · 采集仍可正常进行")
            return
        preview = " · ".join(
            f"{item['name']}={item['value']}" for item in fields[:3]
        )
        if len(fields) > 3:
            preview += f" · +{len(fields) - 3} 项"
        self.project_record_summary.setText(f"已填写 {len(fields)}/10 · {preview}")

    def _apply_resume_plan_to_controls(self, batch) -> None:
        """Show the exact project records frozen with the resumable Batch."""
        super()._apply_resume_plan_to_controls(batch)
        try:
            manifest = load_batch_manifest(Path(batch.manifest_path))
            self._project_user_fields = normalize_user_fields(
                manifest.get("user_fields")
            )
        except (OSError, ValueError):
            self._project_user_fields = ()
        self._refresh_project_record_summary()

    def _set_capture_busy(self, busy: bool) -> None:
        super()._set_capture_busy(busy)
        if hasattr(self, "project_record_button"):
            self.project_record_button.setEnabled(not busy)
        if hasattr(self, "edit_data_records_button"):
            self._refresh_record_actions()

    # ------------------------------------------------------------------
    # Post-capture editing
    # ------------------------------------------------------------------
    def _refresh_record_actions(self) -> None:
        if not hasattr(self, "edit_data_records_button"):
            return
        item = self.data_tree.currentItem() if hasattr(self, "data_tree") else None
        self.edit_data_records_button.setEnabled(not self._capture_busy and item is not None)
        self.directory_records_button.setEnabled(not self._capture_busy)

    def _edit_selected_data_records(self) -> None:
        if self._capture_busy:
            return
        item = self.data_tree.currentItem()
        if item is None:
            return

        manifest_path, _frequency_index, job_id = self._selected_review_context()
        kind, path = self._selected_kind_and_path(item)

        try:
            if job_id and path is not None and path.is_dir():
                current = read_sample_user_fields(path)
                fields = self._run_record_dialog(current, f"编辑样本项目记录 · {path.name}")
                if fields is None:
                    return
                write_sample_user_fields(path, fields, job_id=job_id)
                self.statusBar().showMessage(f"已更新样本项目记录：{path.name}")
                return

            if kind == "batch" and manifest_path is not None:
                manifest = load_batch_manifest(manifest_path)
                current = normalize_user_fields(manifest.get("user_fields"))
                fields = self._run_record_dialog(current, f"编辑 Batch 项目记录 · {manifest_path.parent.name}")
                if fields is None:
                    return
                count = update_batch_user_fields(manifest_path, fields)
                self.statusBar().showMessage(
                    f"已更新 Batch 项目记录，并同步 {count} 个现有样本"
                )
                return

            if path is not None and path.is_dir():
                self._edit_directory_records(path)
                return
        except Exception as exc:
            QMessageBox.warning(self, "项目记录", f"修改失败：{type(exc).__name__}: {exc}")

    def _edit_arbitrary_directory_records(self) -> None:
        if self._capture_busy:
            return
        start = self.output_root_edit.text().strip() or str(Path.home())
        selected = QFileDialog.getExistingDirectory(self, "选择需要修改项目记录的数据目录", start)
        if not selected:
            return
        self._edit_directory_records(Path(selected))

    def _edit_directory_records(self, root: Path) -> None:
        root = Path(root).expanduser().resolve()
        try:
            # If the root itself is a sample, use its fields as the initial value.
            current = read_sample_user_fields(root)
            if not current:
                for sample_info in root.rglob("sample_info.json"):
                    current = read_sample_user_fields(sample_info.parent)
                    if current:
                        break
            fields = self._run_record_dialog(current, f"批量编辑目录项目记录 · {root.name}")
            if fields is None:
                return
            count = update_directory_user_fields(root, fields)
            self.statusBar().showMessage(f"已更新目录项目记录：{count} 个完整样本")
            if count == 0:
                QMessageBox.information(
                    self,
                    "项目记录",
                    "该目录下没有发现包含四个正式 NPZ 的完整配对样本。",
                )
        except Exception as exc:
            QMessageBox.warning(self, "项目记录", f"修改失败：{type(exc).__name__}: {exc}")

    def _run_record_dialog(self, current, title: str):
        dialog = CustomFieldsDialog(current, title=title, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.fields()

    @staticmethod
    def _selected_kind_and_path(item) -> tuple[str | None, Path | None]:
        current = item
        while current is not None:
            kind = current.data(0, _KIND_ROLE)
            raw_path = current.data(0, Qt.ItemDataRole.UserRole)
            if kind in {"job", "recent_job", "frequency", "directory", "batch"} and raw_path:
                path = Path(str(raw_path)).expanduser()
                if path.is_file():
                    path = path.parent
                return str(kind), path
            current = current.parent()
        return None, None
