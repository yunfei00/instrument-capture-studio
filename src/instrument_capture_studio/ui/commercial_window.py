"""Commercial v1 desktop shell with task-oriented navigation pages.

This module intentionally rearranges the already-qualified controls instead of
re-implementing capture behavior. All existing controller, recovery, resume,
reporting and engineering-debug actions remain the same objects; only their
presentation is reorganized into a commercial desktop information architecture.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from instrument_capture_studio.app.capture_recipe import CaptureRecipe, ExecutionMode
from instrument_capture_studio.ui.recipe_alignment_window import (
    MainWindow as RecipeAlignmentWindow,
)


_NAV_ITEMS = (
    ("任务采集", "配置本次任务、执行采集并查看实时进度。"),
    ("仪表连接", "管理 FSW 与 DSO-X 连接和仪表参数。"),
    ("数据与报告", "浏览 Batch / Job、查看曲线并生成报告。"),
    ("配置模板", "保存、加载和维护常用实验配置。"),
    ("工程调试", "单步验证同步链路与现场问题定位。"),
    ("设置与日志", "查看运行日志、路径和产品运行信息。"),
)


class MainWindow(RecipeAlignmentWindow):
    """Release-hardened product UI presented as a commercial multi-page app."""

    def __init__(self) -> None:
        super().__init__()
        self._install_commercial_shell()
        self._apply_commercial_style()
        self._commercial_status_timer = QTimer(self)
        self._commercial_status_timer.setInterval(500)
        self._commercial_status_timer.timeout.connect(self._refresh_quick_status)
        self._commercial_status_timer.start()
        self._sync_recipe_controls()
        self._refresh_quick_status()
        self.statusBar().showMessage("就绪 · v1.0.0 Final RC · 商业版分页界面")

    # ------------------------------------------------------------------
    # Shell construction
    # ------------------------------------------------------------------
    def _install_commercial_shell(self) -> None:
        central = self.centralWidget()
        root = central.layout() if central is not None else None
        if not isinstance(root, QVBoxLayout):
            raise RuntimeError("commercial shell requires the base QVBoxLayout")

        # The legacy window is header + one vertical splitter. All qualified
        # controls live under that splitter. Detach it and re-home those exact
        # widgets into task-oriented pages so behavior stays unchanged.
        legacy_item = root.takeAt(1)
        legacy_splitter = legacy_item.widget() if legacy_item is not None else None
        if legacy_splitter is None:
            raise RuntimeError("legacy desktop splitter was not found")

        fsw_group = self.fsw_resource_edit.parentWidget()
        dsox_group = self.dsox_resource_edit.parentWidget()
        capture_group = self.start_button.parentWidget()
        data_group = self.data_tree.parentWidget()
        log_group = self.log_view.parentWidget()
        if None in (fsw_group, dsox_group, capture_group, data_group, log_group):
            raise RuntimeError("one or more qualified UI groups were not found")

        capture_group.setTitle("采集任务")
        self._extract_secondary_controls(capture_group)

        quick_status = self._build_quick_status_strip(central)
        root.addWidget(quick_status)

        workspace = QWidget(central)
        workspace.setObjectName("commercialWorkspace")
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(14)

        sidebar = self._build_sidebar(workspace)
        self.commercial_stack = QStackedWidget(workspace)
        self.commercial_stack.setObjectName("commercialPageStack")

        task_page, task_body = self._make_page(
            "任务采集",
            "只保留采集 Recipe、执行方式、任务关键参数、开始/暂停/停止与续采状态。",
        )
        instrument_page, instrument_body = self._make_page(
            "仪表连接",
            "连接测试和仪表级参数集中在这里；正式采集页不再堆叠设备连接配置。",
        )
        data_page, data_body = self._make_page(
            "数据与报告",
            "统一浏览正式 Schema 数据、Batch / Job、曲线、HTML 报告和批量导出。",
            scroll=False,
        )
        template_page, template_body = self._make_page(
            "配置模板",
            "把常用测试方案沉淀成模板，避免每次重复填写参数。",
        )
        debug_page, debug_body = self._make_page(
            "工程调试",
            "高级入口，仅用于仪表联调、单步同步验证与现场问题定位。",
        )
        settings_page, settings_body = self._make_page(
            "设置与日志",
            "查看运行日志、会话日志和当前数据路径。",
            scroll=False,
        )

        self._move_group(capture_group, task_body)
        self._build_task_parameter_card(task_body)
        task_body.addStretch(1)

        instrument_grid = QGridLayout()
        instrument_grid.setHorizontalSpacing(14)
        instrument_grid.setVerticalSpacing(14)
        instrument_grid.addWidget(fsw_group, 0, 0)
        instrument_grid.addWidget(dsox_group, 0, 1)
        instrument_grid.setColumnStretch(0, 1)
        instrument_grid.setColumnStretch(1, 1)
        instrument_body.addLayout(instrument_grid)
        instrument_body.addStretch(1)

        self._move_group(data_group, data_body)
        data_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._build_template_page(template_body)
        self._build_debug_page(debug_body)
        self._build_settings_page(settings_body, log_group)

        for page in (
            task_page,
            instrument_page,
            data_page,
            template_page,
            debug_page,
            settings_page,
        ):
            self.commercial_stack.addWidget(page)

        workspace_layout.addWidget(sidebar)
        workspace_layout.addWidget(self.commercial_stack, 1)
        root.addWidget(workspace, 1)

        self.commercial_nav.currentRowChanged.connect(
            self.commercial_stack.setCurrentIndex
        )
        self.commercial_nav.setCurrentRow(0)

        legacy_splitter.hide()
        legacy_splitter.deleteLater()
        self.resize(1380, 860)
        self.setMinimumSize(1120, 720)

    def _extract_secondary_controls(self, capture_group: QWidget) -> None:
        """Remove template/debug/legacy help rows from the primary task card."""
        layout = capture_group.layout()
        if not isinstance(layout, QGridLayout):
            raise RuntimeError("capture group must use QGridLayout")

        self._template_toolbar = self.template_combo.parentWidget()
        self._debug_action_button = self.recipe_debug_button

        if self._template_toolbar is not None:
            layout.removeWidget(self._template_toolbar)
        layout.removeWidget(self._debug_action_button)

        # Row 2 is an old connection-lifecycle explanation. Rows 5 and 9 were
        # inline template and engineering-debug rows. They are secondary in the
        # commercial shell and now have dedicated pages.
        for row in (2, 5, 9):
            for column in range(6):
                item = layout.itemAtPosition(row, column)
                widget = item.widget() if item is not None else None
                if widget is not None:
                    widget.hide()

        if self._template_toolbar is not None:
            self._template_toolbar.show()
        self._debug_action_button.show()

    def _build_task_parameter_card(self, layout: QVBoxLayout) -> None:
        """Move only task-facing parameters out of instrument connection cards."""
        card = QGroupBox("任务关键参数")
        card.setObjectName("taskParameterCard")
        grid = QGridLayout(card)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        fields = (
            self.center_hz_edit,
            self.span_hz_edit,
            self.waveform_channel_spin,
            self.followup_position_edit,
            self.followup_scale_edit,
        )
        for field in fields:
            self._detach_form_field(field)

        self.task_center_label = QLabel("固定频率 Center (Hz)")
        self.task_span_label = QLabel("固定频率 Span (Hz)")
        self.task_channel_label = QLabel("Waveform Channel")
        self.task_followup_position_label = QLabel("第二次 Position (s)")
        self.task_followup_scale_label = QLabel("第二次 Scale (s/div)")

        grid.addWidget(self.task_center_label, 0, 0)
        grid.addWidget(self.center_hz_edit, 0, 1)
        grid.addWidget(self.task_span_label, 0, 2)
        grid.addWidget(self.span_hz_edit, 0, 3)
        grid.addWidget(self.task_channel_label, 1, 0)
        grid.addWidget(self.waveform_channel_spin, 1, 1)
        grid.addWidget(self.task_followup_position_label, 1, 2)
        grid.addWidget(self.followup_position_edit, 1, 3)
        grid.addWidget(self.task_followup_scale_label, 2, 2)
        grid.addWidget(self.followup_scale_edit, 2, 3)

        self.task_parameter_hint = QLabel(card)
        self.task_parameter_hint.setObjectName("commercialHint")
        self.task_parameter_hint.setWordWrap(True)
        grid.addWidget(self.task_parameter_hint, 3, 0, 1, 4)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        self.commercial_task_parameter_card = card
        layout.addWidget(card)

    @staticmethod
    def _detach_form_field(field: QWidget) -> None:
        parent = field.parentWidget()
        form = parent.layout() if parent is not None else None
        if not isinstance(form, QFormLayout):
            return
        label = form.labelForField(field)
        form.removeWidget(field)
        if label is not None:
            form.removeWidget(label)
            label.hide()

    def _build_sidebar(self, parent: QWidget) -> QWidget:
        sidebar = QFrame(parent)
        sidebar.setObjectName("commercialSidebar")
        sidebar.setFixedWidth(190)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(10)

        title = QLabel("工作区", sidebar)
        title.setObjectName("sidebarTitle")
        subtitle = QLabel("Instrument Capture Studio", sidebar)
        subtitle.setObjectName("sidebarSubtitle")
        subtitle.setWordWrap(True)

        self.commercial_nav = QListWidget(sidebar)
        self.commercial_nav.setObjectName("commercialNav")
        self.commercial_nav.setSpacing(3)
        for name, _description in _NAV_ITEMS:
            self.commercial_nav.addItem(name)

        footer = QLabel("v1.0.0 Final RC", sidebar)
        footer.setObjectName("sidebarFooter")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(6)
        layout.addWidget(self.commercial_nav, 1)
        layout.addWidget(footer)
        return sidebar

    def _build_quick_status_strip(self, parent: QWidget) -> QWidget:
        frame = QFrame(parent)
        frame.setObjectName("quickStatusStrip")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        self.quick_fsw_status = QLabel(frame)
        self.quick_fsw_status.setObjectName("quickStatusChip")
        self.quick_dsox_status = QLabel(frame)
        self.quick_dsox_status.setObjectName("quickStatusChip")
        self.quick_job_status = QLabel(frame)
        self.quick_job_status.setObjectName("quickStatusChip")
        self.quick_mode_status = QLabel(frame)
        self.quick_mode_status.setObjectName("quickStatusChip")
        self.quick_data_root = QLabel(frame)
        self.quick_data_root.setObjectName("quickStatusPath")

        layout.addWidget(self.quick_fsw_status)
        layout.addWidget(self.quick_dsox_status)
        layout.addWidget(self.quick_job_status)
        layout.addWidget(self.quick_mode_status)
        layout.addStretch(1)
        layout.addWidget(self.quick_data_root)
        return frame

    def _make_page(
        self,
        title_text: str,
        description: str,
        *,
        scroll: bool = True,
    ) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget(self)
        page.setObjectName("commercialPage")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(4, 0, 4, 4)
        page_layout.setSpacing(10)

        header = QFrame(page)
        header.setObjectName("commercialPageHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(4, 2, 4, 8)
        header_layout.setSpacing(2)
        title = QLabel(title_text, header)
        title.setObjectName("commercialPageTitle")
        note = QLabel(description, header)
        note.setObjectName("commercialPageDescription")
        note.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(note)
        page_layout.addWidget(header)

        if not scroll:
            body = QWidget(page)
            body_layout = QVBoxLayout(body)
            body_layout.setContentsMargins(0, 0, 0, 0)
            body_layout.setSpacing(12)
            page_layout.addWidget(body, 1)
            return page, body_layout

        scroll_area = QScrollArea(page)
        scroll_area.setObjectName("commercialScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget(scroll_area)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 6, 0)
        body_layout.setSpacing(12)
        scroll_area.setWidget(body)
        page_layout.addWidget(scroll_area, 1)
        return page, body_layout

    @staticmethod
    def _move_group(group: QWidget, target_layout: QVBoxLayout) -> None:
        old_parent = group.parentWidget()
        old_layout = old_parent.layout() if old_parent is not None else None
        if old_layout is not None:
            old_layout.removeWidget(group)
        target_layout.addWidget(group)
        group.show()

    def _build_template_page(self, layout: QVBoxLayout) -> None:
        card = QGroupBox("实验配置模板")
        card_layout = QVBoxLayout(card)
        intro = QLabel(
            "模板会保存当前仪表地址、Recipe、执行方式、频率计划、示波器参数和输出目录。"
        )
        intro.setObjectName("commercialHint")
        intro.setWordWrap(True)
        card_layout.addWidget(intro)

        if self._template_toolbar is not None:
            old_parent = self._template_toolbar.parentWidget()
            old_layout = old_parent.layout() if old_parent is not None else None
            if old_layout is not None:
                old_layout.removeWidget(self._template_toolbar)
            card_layout.addWidget(self._template_toolbar)
            self._template_toolbar.show()

        layout.addWidget(card)
        layout.addStretch(1)

    def _build_debug_page(self, layout: QVBoxLayout) -> None:
        card = QGroupBox("工程调试 / 单步采集")
        card_layout = QVBoxLayout(card)
        warning = QLabel(
            "此页面面向研发、交付和售后。正式测试请优先使用“任务采集”；只有需要确认 "
            "Sweep Time、EXT ARM、两次 DSO-X Single 或 Free Run Single 时再进入单步调试。"
        )
        warning.setObjectName("commercialHint")
        warning.setWordWrap(True)
        card_layout.addWidget(warning)

        old_parent = self._debug_action_button.parentWidget()
        old_layout = old_parent.layout() if old_parent is not None else None
        if old_layout is not None:
            old_layout.removeWidget(self._debug_action_button)
        card_layout.addWidget(self._debug_action_button)
        self._debug_action_button.show()
        layout.addWidget(card)
        layout.addStretch(1)

    def _build_settings_page(self, layout: QVBoxLayout, log_group: QWidget) -> None:
        info = QGroupBox("运行信息")
        info_layout = QGridLayout(info)
        info_layout.addWidget(QLabel("当前数据目录"), 0, 0)
        self.settings_data_root_label = QLabel()
        self.settings_data_root_label.setWordWrap(True)
        info_layout.addWidget(self.settings_data_root_label, 0, 1)

        if hasattr(self, "open_session_log_button"):
            button = self.open_session_log_button
            old_parent = button.parentWidget()
            old_layout = old_parent.layout() if old_parent is not None else None
            if old_layout is not None:
                old_layout.removeWidget(button)
            info_layout.addWidget(button, 1, 1)
            button.show()

        layout.addWidget(info)
        self._move_group(log_group, layout)
        log_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        layout.setStretch(layout.count() - 1, 1)

    # ------------------------------------------------------------------
    # Recipe-aware presentation
    # ------------------------------------------------------------------
    def _sync_recipe_controls(self, *_args) -> None:
        super()._sync_recipe_controls(*_args)
        if not hasattr(self, "commercial_task_parameter_card"):
            return
        self._refresh_task_parameter_visibility()
        self._refresh_standalone_dsox_visibility()

    def _sync_sweep_mode(self, *_args) -> None:
        super()._sync_sweep_mode(*_args)
        if hasattr(self, "commercial_task_parameter_card"):
            self._refresh_task_parameter_visibility()

    def _refresh_task_parameter_visibility(self) -> None:
        recipe = self._selected_recipe()
        mode = self._selected_execution_mode()
        paired = recipe is CaptureRecipe.EXT_IMM_PAIR
        dsox_required = recipe in {
            CaptureRecipe.EXT_IMM_PAIR,
            CaptureRecipe.DSOX_ONLY,
        }

        show_fixed_frequency = (
            recipe is CaptureRecipe.IMM_SPECTRUM_ONLY
            or (paired and mode is ExecutionMode.FIXED_REPEAT)
        )
        for label, field in (
            (self.task_center_label, self.center_hz_edit),
            (self.task_span_label, self.span_hz_edit),
        ):
            label.setVisible(show_fixed_frequency)
            field.setVisible(show_fixed_frequency)

        self.task_channel_label.setVisible(dsox_required)
        self.waveform_channel_spin.setVisible(dsox_required)

        for label, field in (
            (self.task_followup_position_label, self.followup_position_edit),
            (self.task_followup_scale_label, self.followup_scale_edit),
        ):
            label.setVisible(paired)
            field.setVisible(paired)

        if paired and mode is ExecutionMode.SINGLE:
            hint = (
                "FSW 测量参数和 Sweep Time 由测试人员在仪表上预先设置；软件实时读取 Sweep Time。"
                "第一次示波器窗口自动计算为 Position=T/2、Scale=T/10。"
            )
        elif paired and mode is ExecutionMode.FREQUENCY_SWEEP:
            hint = (
                "频率计划使用上方起始/结束/步长/Span；每个频点仍实时读取 FSW Sweep Time，"
                "两次 DSO-X 均执行 Single。"
            )
        elif paired:
            hint = (
                "固定频率重复使用这里的 Center/Span 作为任务计划；FSW 其他测量参数由测试前配置，"
                "Sweep Time 每个 Job 实时读取。"
            )
        elif recipe is CaptureRecipe.IMM_SPECTRUM_ONLY:
            hint = "FSW 单采使用 IMM / Free Run 的一次 Single Sweep。"
        else:
            hint = "DSO-X 单采使用所选 Waveform Channel；DELAY/CYCLE 详细参数在“仪表连接”页。"
        self.task_parameter_hint.setText(hint)

    def _refresh_standalone_dsox_visibility(self) -> None:
        recipe = self._selected_recipe()
        standalone = recipe is CaptureRecipe.DSOX_ONLY
        for field in (
            self.delay_source1_edit,
            self.delay_source2_edit,
            self.delay_edge1_combo,
            self.delay_edge2_combo,
            self.cycle_source_edit,
            self.delay_timebase_scale_edit,
            self.cycle_timebase_scale_edit,
        ):
            self._set_form_field_visibility(field, standalone)

        # Trigger source is owned by the formal Recipe (EXT -> IMM, or IMM-only)
        # and is not an operator-facing setting in v1.
        self._set_form_field_visibility(self.trigger_source_combo, False)

    @staticmethod
    def _set_form_field_visibility(field: QWidget, visible: bool) -> None:
        parent = field.parentWidget()
        form = parent.layout() if parent is not None else None
        field.setVisible(visible)
        if isinstance(form, QFormLayout):
            label = form.labelForField(field)
            if label is not None:
                label.setVisible(visible)

    # ------------------------------------------------------------------
    # Lightweight shell status
    # ------------------------------------------------------------------
    def _refresh_quick_status(self) -> None:
        if not hasattr(self, "quick_fsw_status"):
            return
        self.quick_fsw_status.setText(f"FSW · {self.fsw_status_label.text()}")
        self.quick_dsox_status.setText(f"DSO-X · {self.dsox_status_label.text()}")
        self.quick_job_status.setText(f"任务 · {self.job_state_label.text()}")
        self.quick_mode_status.setText(f"模式 · {self.capture_mode_combo.currentText()}")
        root_text = self.output_root_edit.text().strip() or "未设置"
        self.quick_data_root.setText(f"数据 · {root_text}")
        if hasattr(self, "settings_data_root_label"):
            self.settings_data_root_label.setText(root_text)

    def _apply_commercial_style(self) -> None:
        self.setStyleSheet(
            self.styleSheet()
            + """
            QFrame#commercialSidebar {
                background: #1f2937;
                border-radius: 10px;
            }
            QLabel#sidebarTitle {
                color: white;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#sidebarSubtitle, QLabel#sidebarFooter {
                color: #aeb8c5;
                font-size: 11px;
            }
            QListWidget#commercialNav {
                background: transparent;
                color: #dce3eb;
                border: none;
                outline: none;
                font-size: 14px;
            }
            QListWidget#commercialNav::item {
                min-height: 40px;
                padding-left: 12px;
                border-radius: 7px;
            }
            QListWidget#commercialNav::item:hover {
                background: #2d3948;
            }
            QListWidget#commercialNav::item:selected {
                background: #3b82f6;
                color: white;
                font-weight: 600;
            }
            QFrame#quickStatusStrip {
                background: #f7f9fc;
                border: 1px solid #dbe2ea;
                border-radius: 8px;
            }
            QLabel#quickStatusChip {
                background: white;
                border: 1px solid #dbe2ea;
                border-radius: 6px;
                padding: 5px 10px;
                font-weight: 600;
            }
            QLabel#quickStatusPath {
                color: #5f6b7a;
                padding: 4px;
            }
            QLabel#commercialPageTitle {
                font-size: 20px;
                font-weight: 700;
            }
            QLabel#commercialPageDescription, QLabel#commercialHint {
                color: #667085;
            }
            QGroupBox#taskParameterCard {
                border-color: #cbd5e1;
            }
            QScrollArea#commercialScrollArea {
                background: transparent;
            }
            """
        )
