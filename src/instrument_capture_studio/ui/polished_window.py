"""Commercial visual polish layered on the qualified paged desktop shell.

This module deliberately changes presentation only.  It re-homes the already
qualified task controls into a clearer operator dashboard, adds read-only
configuration/status summaries, and strengthens visual hierarchy without
changing capture, resume, recovery, reporting, or instrument-control behavior.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from instrument_capture_studio.app.capture_recipe import CaptureRecipe, ExecutionMode
from instrument_capture_studio.ui.commercial_window import MainWindow as CommercialWindow


class MainWindow(CommercialWindow):
    """Final-RC commercial shell with operator-focused task-page polish."""

    def __init__(self) -> None:
        super().__init__()
        self._install_polished_task_dashboard()
        self._apply_polished_style()
        self._refresh_quick_status()
        self.resize(1440, 900)
        self.setMinimumSize(1180, 760)
        self.statusBar().showMessage("就绪 · v1.0.0 Final RC · 商业版工作台")

    # ------------------------------------------------------------------
    # Task dashboard
    # ------------------------------------------------------------------
    def _install_polished_task_dashboard(self) -> None:
        task_page = self.commercial_stack.widget(0)
        if task_page is None:
            raise RuntimeError("commercial task page was not found")

        scroll = task_page.findChild(QScrollArea, "commercialScrollArea")
        body = scroll.widget() if scroll is not None else None
        task_layout = body.layout() if body is not None else None
        if not isinstance(task_layout, QVBoxLayout):
            raise RuntimeError("commercial task page body must use QVBoxLayout")

        capture_group = self.start_button.parentWidget()
        parameter_card = self.commercial_task_parameter_card
        if capture_group is None or parameter_card is None:
            raise RuntimeError("commercial task controls were not found")

        # Remove the two top-level task widgets and the old trailing stretch.
        # The exact widgets are re-used below; no signal/slot wiring is changed.
        while task_layout.count():
            task_layout.takeAt(0)

        dashboard = QWidget(body)
        dashboard.setObjectName("polishedTaskDashboard")
        grid = QGridLayout(dashboard)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        primary = QWidget(dashboard)
        primary.setObjectName("taskPrimaryColumn")
        primary_layout = QVBoxLayout(primary)
        primary_layout.setContentsMargins(0, 0, 0, 0)
        primary_layout.setSpacing(12)

        capture_group.setTitle("采集方案与执行参数")
        primary_layout.addWidget(capture_group)
        primary_layout.addWidget(parameter_card)
        primary_layout.addStretch(1)

        side = QWidget(dashboard)
        side.setObjectName("taskSideColumn")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(12)

        self._build_task_control_card(side_layout, capture_group)
        self._build_task_summary_card(side_layout, capture_group)
        side_layout.addStretch(1)

        grid.addWidget(primary, 0, 0)
        grid.addWidget(side, 0, 1)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        grid.setColumnMinimumWidth(1, 330)

        task_layout.addWidget(dashboard, 1)

    def _build_task_control_card(
        self,
        target_layout: QVBoxLayout,
        capture_group: QWidget,
    ) -> None:
        capture_layout = capture_group.layout()
        if not isinstance(capture_layout, QGridLayout):
            raise RuntimeError("capture group must use QGridLayout")

        widgets = (
            self.job_state_label,
            self.progress_bar,
            self.start_button,
            self.pause_button,
            self.stop_button,
            self.resume_previous_button,
            self.resume_summary_label,
        )
        for widget in widgets:
            capture_layout.removeWidget(widget)

        # The old row captions are presentation-only labels.  The qualified
        # controls themselves are moved into the dedicated status/action card.
        self._hide_remaining_grid_row(capture_layout, 1)
        self._hide_remaining_grid_row(capture_layout, 8)

        card = QGroupBox("任务控制与状态")
        card.setObjectName("taskControlCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 18, 14, 14)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        state_caption = QLabel("当前状态")
        state_caption.setObjectName("taskFieldCaption")
        self.job_state_label.setObjectName("taskLiveState")
        grid.addWidget(state_caption, 0, 0)
        grid.addWidget(self.job_state_label, 0, 1, 1, 2)

        progress_caption = QLabel("任务进度")
        progress_caption.setObjectName("taskFieldCaption")
        grid.addWidget(progress_caption, 1, 0)
        grid.addWidget(self.progress_bar, 1, 1, 1, 2)

        actions = QWidget(card)
        actions.setObjectName("taskActionBar")
        action_layout = QHBoxLayout(actions)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)

        self.start_button.setProperty("commercialRole", "primary")
        self.pause_button.setProperty("commercialRole", "secondary")
        self.stop_button.setProperty("commercialRole", "danger")
        action_layout.addWidget(self.start_button, 2)
        action_layout.addWidget(self.pause_button, 1)
        action_layout.addWidget(self.stop_button, 1)
        grid.addWidget(actions, 2, 0, 1, 3)

        separator = QFrame(card)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("taskSeparator")
        grid.addWidget(separator, 3, 0, 1, 3)

        resume_caption = QLabel("未完成任务")
        resume_caption.setObjectName("taskFieldCaption")
        self.resume_previous_button.setProperty("commercialRole", "quiet")
        self.resume_summary_label.setObjectName("taskResumeSummary")
        self.resume_summary_label.setWordWrap(True)
        grid.addWidget(resume_caption, 4, 0)
        grid.addWidget(self.resume_previous_button, 4, 1, 1, 2)
        grid.addWidget(self.resume_summary_label, 5, 0, 1, 3)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        self.commercial_task_control_card = card
        target_layout.addWidget(card)

    def _build_task_summary_card(
        self,
        target_layout: QVBoxLayout,
        capture_group: QWidget,
    ) -> None:
        capture_layout = capture_group.layout()
        if not isinstance(capture_layout, QGridLayout):
            raise RuntimeError("capture group must use QGridLayout")

        # The long workflow sentence no longer competes with the input controls.
        # It remains the same live QLabel and still receives all existing updates.
        capture_layout.removeWidget(self.recipe_summary_label)

        card = QGroupBox("本次配置摘要")
        card.setObjectName("taskSummaryCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 18, 14, 14)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        self.task_summary_recipe = self._summary_value_label()
        self.task_summary_mode = self._summary_value_label()
        self.task_summary_frequency = self._summary_value_label()
        self.task_summary_channel = self._summary_value_label()
        self.task_summary_followup = self._summary_value_label()
        self.task_summary_output = self._summary_value_label()
        self.task_summary_output.setWordWrap(True)

        rows = (
            ("采集内容", self.task_summary_recipe),
            ("执行方式", self.task_summary_mode),
            ("频率计划", self.task_summary_frequency),
            ("示波器通道", self.task_summary_channel),
            ("第二次采集", self.task_summary_followup),
            ("数据目录", self.task_summary_output),
        )
        for row, (caption, value) in enumerate(rows):
            label = QLabel(caption)
            label.setObjectName("taskFieldCaption")
            grid.addWidget(label, row, 0)
            grid.addWidget(value, row, 1)

        separator = QFrame(card)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("taskSeparator")
        grid.addWidget(separator, len(rows), 0, 1, 2)

        flow_caption = QLabel("采集流程说明")
        flow_caption.setObjectName("taskFieldCaption")
        self.recipe_summary_label.setObjectName("taskFlowDescription")
        self.recipe_summary_label.setWordWrap(True)
        grid.addWidget(flow_caption, len(rows) + 1, 0, 1, 2)
        grid.addWidget(self.recipe_summary_label, len(rows) + 2, 0, 1, 2)

        grid.setColumnStretch(1, 1)
        self.commercial_task_summary_card = card
        target_layout.addWidget(card)

    @staticmethod
    def _summary_value_label() -> QLabel:
        label = QLabel("—")
        label.setObjectName("taskSummaryValue")
        label.setTextInteractionFlags(label.textInteractionFlags())
        return label

    @staticmethod
    def _hide_remaining_grid_row(layout: QGridLayout, row: int) -> None:
        for column in range(layout.columnCount()):
            item = layout.itemAtPosition(row, column)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.hide()

    # ------------------------------------------------------------------
    # Live summary / status presentation
    # ------------------------------------------------------------------
    def _refresh_quick_status(self) -> None:
        super()._refresh_quick_status()
        if not hasattr(self, "commercial_task_summary_card"):
            return

        self._refresh_task_summary()
        self._refresh_status_tones()

        root_text = self.output_root_edit.text().strip() or "未设置"
        self.quick_data_root.setToolTip(root_text)
        self.quick_data_root.setText(f"数据 · {self._compact_text(root_text, 48)}")
        self.quick_data_root.setMaximumWidth(430)

    def _refresh_task_summary(self) -> None:
        recipe = self._selected_recipe()
        mode = self._selected_execution_mode()
        paired = recipe is CaptureRecipe.EXT_IMM_PAIR
        dsox_required = recipe in {
            CaptureRecipe.EXT_IMM_PAIR,
            CaptureRecipe.DSOX_ONLY,
        }

        self.task_summary_recipe.setText(self.recipe_combo.currentText())
        self.task_summary_mode.setText(self.capture_mode_combo.currentText())
        self.task_summary_frequency.setText(self._frequency_summary(recipe, mode))
        self.task_summary_channel.setText(
            f"CH{self.waveform_channel_spin.value()}" if dsox_required else "—"
        )
        if paired:
            position = self.followup_position_edit.text().strip() or "—"
            scale = self.followup_scale_edit.text().strip() or "—"
            self.task_summary_followup.setText(
                f"Position {position} s · Scale {scale} s/div"
            )
        else:
            self.task_summary_followup.setText("—")

        output = self.output_root_edit.text().strip() or "未设置"
        self.task_summary_output.setText(output)
        self.task_summary_output.setToolTip(output)

    def _frequency_summary(
        self,
        recipe: CaptureRecipe,
        mode: ExecutionMode,
    ) -> str:
        if recipe is CaptureRecipe.DSOX_ONLY:
            return "—"

        if recipe is CaptureRecipe.EXT_IMM_PAIR and mode is ExecutionMode.SINGLE:
            return "沿用 FSW 当前测量设置"

        if recipe is CaptureRecipe.EXT_IMM_PAIR and mode is ExecutionMode.FREQUENCY_SWEEP:
            start = self.sweep_start_mhz_edit.text().strip() or "—"
            stop = self.sweep_stop_mhz_edit.text().strip() or "—"
            step = self.sweep_step_mhz_edit.text().strip() or "—"
            span = self.sweep_span_mhz_edit.text().strip() or "—"
            count = self.sweep_capture_count_spin.value()
            return (
                f"{start}–{stop} MHz · 步长 {step} MHz · "
                f"Span {span} MHz · 每频点 {count} 次"
            )

        center = self._mhz_from_hz_field(self.center_hz_edit.text())
        span = self._mhz_from_hz_field(self.span_hz_edit.text())
        if recipe is CaptureRecipe.EXT_IMM_PAIR:
            return (
                f"固定 {center} MHz · Span {span} MHz · "
                f"连续 {self.repeat_capture_count_spin.value()} 次"
            )
        return f"Center {center} MHz · Span {span} MHz"

    @staticmethod
    def _mhz_from_hz_field(raw: str) -> str:
        text = raw.strip()
        if not text:
            return "—"
        try:
            return f"{float(text) / 1e6:g}"
        except ValueError:
            return text

    def _refresh_status_tones(self) -> None:
        self._set_tone(
            self.quick_fsw_status,
            self._instrument_tone(self.fsw_status_label.text()),
        )
        self._set_tone(
            self.quick_dsox_status,
            self._instrument_tone(self.dsox_status_label.text()),
        )
        self._set_tone(
            self.quick_job_status,
            self._task_tone(self.job_state_label.text()),
        )
        self._set_tone(self.quick_mode_status, "info")

        state_tone = self._task_tone(self.job_state_label.text())
        self._set_tone(self.job_state_label, state_tone)

    @staticmethod
    def _instrument_tone(text: str) -> str:
        value = text.strip().lower()
        if any(token in value for token in ("可用", "connected", "ready")):
            return "ok"
        if any(token in value for token in ("测试中", "connecting", "busy")):
            return "busy"
        if any(token in value for token in ("失败", "error", "不可用", "断开")):
            return "bad"
        return "idle"

    @staticmethod
    def _task_tone(text: str) -> str:
        value = text.strip().lower()
        if any(token in value for token in ("fail", "error")):
            return "bad"
        if any(token in value for token in ("cancel", "stopping")):
            return "warn"
        if any(token in value for token in ("pause", "reconnect")):
            return "warn"
        if any(
            token in value
            for token in ("running", "starting", "resuming", "busy")
        ):
            return "busy"
        if any(token in value for token in ("success", "completed", "succeeded")):
            return "ok"
        return "idle"

    @staticmethod
    def _set_tone(label: QLabel, tone: str) -> None:
        if label.property("tone") == tone:
            return
        label.setProperty("tone", tone)
        style = label.style()
        style.unpolish(label)
        style.polish(label)
        label.update()

    @staticmethod
    def _compact_text(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        head = max(8, (limit - 3) // 2)
        tail = max(8, limit - 3 - head)
        return f"{text[:head]}...{text[-tail:]}"

    # ------------------------------------------------------------------
    # Visual hierarchy
    # ------------------------------------------------------------------
    def _apply_polished_style(self) -> None:
        self.setStyleSheet(
            self.styleSheet()
            + """
            QWidget#polishedTaskDashboard {
                background: transparent;
            }
            QGroupBox#taskControlCard,
            QGroupBox#taskSummaryCard {
                background: #ffffff;
                border: 1px solid #d8e0e8;
                border-radius: 9px;
                margin-top: 10px;
                font-weight: 650;
            }
            QGroupBox#taskControlCard::title,
            QGroupBox#taskSummaryCard::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
            }
            QLabel#taskFieldCaption {
                color: #667085;
                font-size: 12px;
                font-weight: 500;
            }
            QLabel#taskSummaryValue {
                color: #1f2937;
                font-weight: 600;
            }
            QLabel#taskFlowDescription,
            QLabel#taskResumeSummary {
                color: #667085;
                font-size: 12px;
                line-height: 1.35;
            }
            QLabel#taskLiveState {
                border: 1px solid #dbe2ea;
                border-radius: 6px;
                padding: 5px 9px;
                font-weight: 700;
            }
            QLabel#taskLiveState[tone="busy"] {
                background: #eff6ff;
                border-color: #93c5fd;
                color: #1d4ed8;
            }
            QLabel#taskLiveState[tone="ok"] {
                background: #ecfdf3;
                border-color: #86efac;
                color: #166534;
            }
            QLabel#taskLiveState[tone="warn"] {
                background: #fffbeb;
                border-color: #fcd34d;
                color: #92400e;
            }
            QLabel#taskLiveState[tone="bad"] {
                background: #fef2f2;
                border-color: #fca5a5;
                color: #991b1b;
            }
            QFrame#taskSeparator {
                color: #e5e7eb;
                background: #e5e7eb;
                max-height: 1px;
            }
            QLabel#quickStatusChip[tone="ok"] {
                background: #ecfdf3;
                border-color: #86efac;
                color: #166534;
            }
            QLabel#quickStatusChip[tone="busy"] {
                background: #eff6ff;
                border-color: #93c5fd;
                color: #1d4ed8;
            }
            QLabel#quickStatusChip[tone="warn"] {
                background: #fffbeb;
                border-color: #fcd34d;
                color: #92400e;
            }
            QLabel#quickStatusChip[tone="bad"] {
                background: #fef2f2;
                border-color: #fca5a5;
                color: #991b1b;
            }
            QLabel#quickStatusChip[tone="info"] {
                background: #f5f3ff;
                border-color: #c4b5fd;
                color: #5b21b6;
            }
            QStackedWidget#commercialPageStack QLineEdit,
            QStackedWidget#commercialPageStack QComboBox,
            QStackedWidget#commercialPageStack QSpinBox {
                min-height: 28px;
            }
            QStackedWidget#commercialPageStack QPushButton {
                min-height: 30px;
                padding: 3px 11px;
            }
            QPushButton[commercialRole="primary"] {
                min-height: 38px;
                background: #2563eb;
                color: white;
                border: 1px solid #1d4ed8;
                border-radius: 6px;
                font-weight: 700;
                padding: 4px 16px;
            }
            QPushButton[commercialRole="primary"]:hover {
                background: #1d4ed8;
            }
            QPushButton[commercialRole="primary"]:disabled {
                background: #bfdbfe;
                border-color: #bfdbfe;
                color: #f8fafc;
            }
            QPushButton[commercialRole="danger"] {
                min-height: 36px;
                background: #ffffff;
                color: #b42318;
                border: 1px solid #f0b5ad;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton[commercialRole="secondary"],
            QPushButton[commercialRole="quiet"] {
                min-height: 36px;
                background: #ffffff;
                border: 1px solid #cfd8e3;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton[commercialRole="quiet"] {
                color: #344054;
            }
            QProgressBar {
                min-height: 22px;
                border: 1px solid #d7dee7;
                border-radius: 5px;
                text-align: center;
                background: #f8fafc;
            }
            QProgressBar::chunk {
                border-radius: 4px;
            }
            """
        )
