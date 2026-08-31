"""Delivery-ready visual refinements for the desktop workspace.

This layer keeps qualified capture, resume, recovery, reporting and VISA
behavior intact while tightening the operator-facing pages. The data page also
provides a master/detail browser: select an item on the left and the right pane
updates immediately, while double-click still opens the existing large viewer.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from instrument_capture_studio.app.capture_recipe import CaptureRecipe
from instrument_capture_studio.ui.trace_viewer import TraceChartWidget
from instrument_capture_studio.ui.workspace_window import MainWindow as WorkspaceWindow


class MainWindow(WorkspaceWindow):
    """Final operator-facing desktop shell for delivery review."""

    def __init__(self) -> None:
        super().__init__()
        self._install_delivery_refinement()
        self._install_data_preview_workspace()
        self._refresh_connection_card_visibility()
        self._refresh_delivery_flow_summary()
        self._refresh_data_empty_hint()
        self.statusBar().showMessage("就绪")

    # ------------------------------------------------------------------
    # Parent hooks: preserve behavior, then tighten presentation
    # ------------------------------------------------------------------
    def _sync_recipe_controls(self, *_args) -> None:
        super()._sync_recipe_controls(*_args)
        if hasattr(self, "fsw_identity_label"):
            self._refresh_connection_card_visibility()

    def _update_recipe_summary(self, *_args) -> None:
        super()._update_recipe_summary(*_args)
        if hasattr(self, "recipe_summary_label"):
            self._refresh_delivery_flow_summary()

    def _on_instrument_tested(self, key: str, payload: dict) -> None:
        super()._on_instrument_tested(key, payload)
        self._set_instrument_identity(key, payload)

    def _on_instrument_test_failed(
        self,
        key: str,
        error_type: str,
        message: str,
    ) -> None:
        super()._on_instrument_test_failed(key, error_type, message)
        label = self._identity_label_for(key)
        if label is not None:
            label.setText("连接测试失败 · 请检查 VISA 地址与物理链路")
            label.setToolTip(f"{error_type}: {message}")

    def _refresh_data_empty_hint(self) -> None:
        """Use a deliberate empty state instead of a mostly blank result tree."""
        super()._refresh_data_empty_hint()
        if not hasattr(self, "data_empty_hint") or not hasattr(self, "data_tree"):
            return

        empty = self.data_tree.topLevelItemCount() == 0
        if not empty:
            first = self.data_tree.topLevelItem(0)
            empty = first is not None and first.text(0) == "暂无数据"

        self.data_tree.setVisible(not empty)
        self.data_empty_hint.setVisible(empty)
        if empty:
            self.data_empty_hint.setText(
                "当前数据目录暂无可浏览的 Batch / Job\n"
                "完成一次采集后，结果会自动出现在这里。"
            )
            self.data_empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.data_empty_hint.setMinimumHeight(96)
            if hasattr(self, "data_preview_placeholder"):
                self._show_data_placeholder(
                    "完成一次采集，或选择已有数据目录后，右侧会自动预览曲线和 JSON。"
                )

    # ------------------------------------------------------------------
    # Installation
    # ------------------------------------------------------------------
    def _install_delivery_refinement(self) -> None:
        self._rename_operator_labels()
        self._localize_fsw_parameter_labels()
        self._install_instrument_identity_rows()
        self._rehome_workspace_instrument_hints()

    def _rename_operator_labels(self) -> None:
        group = self.capture_mode_combo.parentWidget()
        layout = group.layout() if group is not None else None
        if isinstance(layout, QGridLayout):
            item = layout.itemAtPosition(3, 0)
            label = item.widget() if item is not None else None
            if isinstance(label, QLabel):
                label.setText("执行方式")
                self.capture_mode_caption = label

    def _localize_fsw_parameter_labels(self) -> None:
        params = self.rbw_hz_edit.parentWidget()
        form = params.layout() if params is not None else None
        if not isinstance(form, QFormLayout):
            return

        labels = (
            (self.rbw_hz_edit, "分辨率带宽 RBW (Hz)"),
            (self.vbw_hz_edit, "视频带宽 VBW (Hz)"),
            (self.fsw_timeout_edit, "步骤超时 (s)"),
        )
        for field, text in labels:
            label = form.labelForField(field)
            if isinstance(label, QLabel):
                label.setText(text)

    def _install_instrument_identity_rows(self) -> None:
        self.fsw_identity_label = self._make_identity_label(
            "连接后显示型号、序列号与固件版本"
        )
        self.dsox_identity_label = self._make_identity_label(
            "连接后显示型号、序列号与固件版本"
        )

        for group, identity in (
            (self.fsw_resource_edit.parentWidget(), self.fsw_identity_label),
            (self.dsox_resource_edit.parentWidget(), self.dsox_identity_label),
        ):
            layout = group.layout() if group is not None else None
            if isinstance(layout, QGridLayout):
                layout.addWidget(identity, 3, 0, 1, 4)

    @staticmethod
    def _make_identity_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("instrumentIdentity")
        label.setWordWrap(True)
        label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        label.setMinimumHeight(38)
        label.setMaximumHeight(46)
        return label

    def _rehome_workspace_instrument_hints(self) -> None:
        for group, hint in (
            (self.fsw_resource_edit.parentWidget(), self.fsw_workspace_hint),
            (self.dsox_resource_edit.parentWidget(), self.dsox_workspace_hint),
        ):
            layout = group.layout() if group is not None else None
            if isinstance(layout, QGridLayout):
                hint.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Fixed,
                )
                hint.setMinimumHeight(48)
                hint.setMaximumHeight(68)
                layout.addWidget(hint, 4, 0, 1, 4)
                layout.setRowStretch(5, 1)

    def _install_data_preview_workspace(self) -> None:
        """Turn the result page into a left navigation + right live preview."""
        group = self.data_tree.parentWidget()
        layout = group.layout() if group is not None else None
        if not isinstance(layout, QVBoxLayout):
            return

        layout.removeWidget(self.data_empty_hint)
        layout.removeWidget(self.data_tree)

        splitter = QSplitter(Qt.Orientation.Horizontal, group)
        splitter.setObjectName("dataPreviewSplitter")
        splitter.setChildrenCollapsible(False)

        left = QWidget(splitter)
        left.setObjectName("dataBrowserPane")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(self.data_empty_hint)
        left_layout.addWidget(self.data_tree, 1)

        preview_card = QGroupBox("即时预览", splitter)
        preview_card.setObjectName("dataPreviewCard")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(12, 16, 12, 12)
        preview_layout.setSpacing(8)

        self.data_preview_title = QLabel("请选择左侧 Batch / Job / 文件")
        self.data_preview_title.setObjectName("dataPreviewTitle")
        self.data_preview_title.setWordWrap(True)

        self.data_preview_path = QLabel("")
        self.data_preview_path.setObjectName("dataPreviewPath")
        self.data_preview_path.setWordWrap(True)
        self.data_preview_path.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.data_preview_stack = QStackedWidget(preview_card)
        self.data_preview_stack.setObjectName("dataPreviewStack")

        self.data_preview_placeholder = QLabel(
            "单击左侧项目即可在这里查看。\n"
            "NPZ 显示曲线，JSON 显示结构化内容，CSV 显示数据片段。\n"
            "双击仍可打开独立大窗口。"
        )
        self.data_preview_placeholder.setObjectName("dataPreviewPlaceholder")
        self.data_preview_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.data_preview_placeholder.setWordWrap(True)

        self.data_trace_preview = TraceChartWidget(preview_card)
        self.data_text_preview = QPlainTextEdit(preview_card)
        self.data_text_preview.setObjectName("dataTextPreview")
        self.data_text_preview.setReadOnly(True)

        self.data_preview_stack.addWidget(self.data_preview_placeholder)
        self.data_preview_stack.addWidget(self.data_trace_preview)
        self.data_preview_stack.addWidget(self.data_text_preview)

        preview_layout.addWidget(self.data_preview_title)
        preview_layout.addWidget(self.data_preview_path)
        preview_layout.addWidget(self.data_preview_stack, 1)

        splitter.addWidget(left)
        splitter.addWidget(preview_card)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        splitter.setSizes([430, 760])

        self.data_preview_splitter = splitter
        layout.addWidget(splitter, 1)
        self.data_tree.itemSelectionChanged.connect(self._preview_selected_data_item)

    # ------------------------------------------------------------------
    # Data page interaction
    # ------------------------------------------------------------------
    def _preview_selected_data_item(self) -> None:
        item = self.data_tree.currentItem()
        if item is None:
            self._show_data_placeholder()
            return

        raw_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not raw_path:
            self._show_data_text(
                item.text(0),
                item.text(1) or "请选择其下的 Batch、Job 或数据文件。",
                None,
            )
            return

        path = Path(str(raw_path))
        if not path.exists():
            self._show_data_text("文件不存在", str(path), path)
            return

        try:
            if path.is_dir():
                job_manifest = path / "job.json"
                if job_manifest.exists():
                    self._show_json_preview(job_manifest, title=f"Job · {path.name}")
                else:
                    entries = sorted(child.name for child in path.iterdir())[:100]
                    text = "目录内容：\n\n" + "\n".join(entries)
                    self._show_data_text(f"目录 · {path.name}", text, path)
                return

            suffix = path.suffix.lower()
            if suffix == ".npz":
                preview = self.data_trace_preview.load_path(path)
                self.data_preview_title.setText(preview.title)
                self.data_preview_path.setText(str(path))
                self.data_preview_stack.setCurrentWidget(self.data_trace_preview)
                return
            if suffix == ".json":
                self._show_json_preview(path)
                return
            if suffix == ".csv":
                lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
                shown = lines[:250]
                if len(lines) > len(shown):
                    shown.append(f"… 仅预览前 {len(shown)} 行，共 {len(lines)} 行")
                self._show_data_text(path.name, "\n".join(shown), path)
                return

            self._show_data_text(path.name, str(path), path)
        except Exception as exc:
            self._show_data_text(
                "预览失败",
                f"{type(exc).__name__}: {exc}",
                path,
            )

    def _show_json_preview(self, path: Path, *, title: str | None = None) -> None:
        value = json.loads(path.read_text(encoding="utf-8"))
        text = json.dumps(value, ensure_ascii=False, indent=2)
        self._show_data_text(title or path.name, text, path)

    def _show_data_text(
        self,
        title: str,
        text: str,
        path: Path | None,
    ) -> None:
        self.data_preview_title.setText(title)
        self.data_preview_path.setText("" if path is None else str(path))
        self.data_text_preview.setPlainText(text)
        self.data_preview_stack.setCurrentWidget(self.data_text_preview)

    def _show_data_placeholder(self, message: str | None = None) -> None:
        if not hasattr(self, "data_preview_placeholder"):
            return
        self.data_preview_title.setText("请选择左侧 Batch / Job / 文件")
        self.data_preview_path.clear()
        if message is not None:
            self.data_preview_placeholder.setText(message)
        self.data_preview_stack.setCurrentWidget(self.data_preview_placeholder)

    # ------------------------------------------------------------------
    # Dynamic presentation
    # ------------------------------------------------------------------
    def _refresh_connection_card_visibility(self) -> None:
        recipe = self._selected_recipe()
        requires_fsw = recipe in {
            CaptureRecipe.EXT_IMM_PAIR,
            CaptureRecipe.IMM_SPECTRUM_ONLY,
        }
        requires_dsox = recipe in {
            CaptureRecipe.EXT_IMM_PAIR,
            CaptureRecipe.DSOX_ONLY,
        }

        fsw_params = self.rbw_hz_edit.parentWidget()
        if fsw_params is not None:
            fsw_params.setVisible(requires_fsw)

        dsox_params = self.delay_source1_edit.parentWidget()
        if dsox_params is not None:
            dsox_params.setVisible(recipe is CaptureRecipe.DSOX_ONLY)

        self.fsw_identity_label.setVisible(requires_fsw)
        self.fsw_workspace_hint.setVisible(requires_fsw)
        self.dsox_identity_label.setVisible(requires_dsox)
        self.dsox_workspace_hint.setVisible(requires_dsox)

    def _refresh_delivery_flow_summary(self) -> None:
        if not hasattr(self, "recipe_summary_label") or not hasattr(self, "recipe_combo"):
            return

        full_text = self.recipe_summary_label.text().strip()
        if full_text:
            self.recipe_summary_label.setToolTip(full_text)

        recipe = self._selected_recipe()
        if recipe is CaptureRecipe.EXT_IMM_PAIR:
            compact = (
                "FSW Sweep Time → DSO-X Single #1 → EXT 读取 → "
                "DSO-X Single #2 → FSW Free Run Single"
            )
        elif recipe is CaptureRecipe.IMM_SPECTRUM_ONLY:
            compact = "FSW IMM / Free Run Single → 保存频谱"
        else:
            compact = "DSO-X DELAY Single → 保存 → CYCLE Single → 保存"
        self.recipe_summary_label.setText(compact)

    def _set_instrument_identity(self, key: str, payload: dict) -> None:
        label = self._identity_label_for(key)
        if label is None:
            return
        model = str(payload.get("model") or "未知型号")
        serial = str(payload.get("serial_number") or "—")
        firmware = str(payload.get("firmware_version") or "—")
        label.setText(f"型号 {model}   ·   序列号 {serial}   ·   固件 {firmware}")
        label.setToolTip(
            "\n".join(
                (
                    f"型号：{model}",
                    f"序列号：{serial}",
                    f"固件：{firmware}",
                    f"地址：{payload.get('address') or '—'}",
                )
            )
        )

    def _identity_label_for(self, key: str) -> QLabel | None:
        if key == "fsw":
            return getattr(self, "fsw_identity_label", None)
        if key == "dsox":
            return getattr(self, "dsox_identity_label", None)
        return None

    # ------------------------------------------------------------------
    # Final visual details
    # ------------------------------------------------------------------
    def _apply_workspace_style(self) -> None:
        super()._apply_workspace_style()
        self.setStyleSheet(
            self.styleSheet()
            + """
            QLabel#instrumentIdentity {
                background: #f7f9fc;
                color: #344054;
                border: 1px solid #dfe6ee;
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#taskFlowDescription {
                padding: 8px 10px;
                background: #f8fafc;
                border: 1px solid #e4e9ef;
                border-radius: 6px;
                color: #475467;
                font-size: 12px;
            }
            QLabel#dataEmptyHint {
                background: #f8fbff;
                color: #315b8a;
                border: 1px dashed #bfd5ee;
                border-radius: 9px;
                padding: 18px;
                font-size: 13px;
            }
            QGroupBox#dataPreviewCard {
                background: #ffffff;
                border: 1px solid #d8e0e8;
                border-radius: 9px;
                margin-top: 10px;
                font-weight: 650;
            }
            QGroupBox#dataPreviewCard::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
            }
            QLabel#dataPreviewTitle {
                color: #25364a;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#dataPreviewPath,
            QLabel#tracePreviewSummary {
                color: #667085;
                font-size: 11px;
            }
            QLabel#dataPreviewPlaceholder {
                background: #f8fafc;
                color: #667085;
                border: 1px dashed #d6dee8;
                border-radius: 8px;
                padding: 24px;
                font-size: 13px;
            }
            QPlainTextEdit#dataTextPreview {
                background: #fbfcfe;
                border: 1px solid #e1e7ef;
                border-radius: 6px;
                padding: 8px;
                font-family: Consolas, Menlo, monospace;
                font-size: 11px;
            }
            QSplitter#dataPreviewSplitter::handle {
                width: 6px;
                background: #eef2f6;
            }
            """
        )
