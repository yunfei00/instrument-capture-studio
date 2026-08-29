"""Final recipe-alignment window with commercial multi-page navigation."""

from dataclasses import replace

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from instrument_capture_studio.app.capture_recipe import CaptureRecipe, ExecutionMode
from instrument_capture_studio.ui.recipe_debug_dialog import RecipeDebugDialog
from instrument_capture_studio.ui.release_window import MainWindow as ReleaseWindow


_NAVIGATION_ITEMS = (
    ("任务采集", "配置采集内容、执行方式、批量参数并控制当前任务。"),
    ("仪表连接", "管理 FSW 与 DSO-X 的 VISA 地址、参数和连接测试。"),
    ("数据与报告", "浏览 Batch / Job、预览数据并生成报告或批量导出曲线。"),
    ("配置模板", "保存、加载和维护可复用的实验采集配置。"),
    ("工程调试", "用于现场联调和问题定位的八步单步采集工具。"),
    ("设置与日志", "查看会话日志与当前客户端运行信息。"),
)


class MainWindow(ReleaseWindow):
    """Release-hardened UI for the hardware-qualified final paired recipe."""

    def __init__(self) -> None:
        self._recipe_debug_dialog: RecipeDebugDialog | None = None
        super().__init__()
        self._install_final_paired_timing_controls()
        self._install_recipe_debug_action()
        # The final controls are created after the parent preference restore.
        self._preferences.restore(self)
        self.followup_position_edit.editingFinished.connect(self._save_preferences)
        self.followup_scale_edit.editingFinished.connect(self._save_preferences)
        self.followup_position_edit.textChanged.connect(self._update_recipe_summary)
        self.followup_scale_edit.textChanged.connect(self._update_recipe_summary)
        self._sync_recipe_controls()

        # The hardware/workflow implementation is intentionally left untouched;
        # this shell only reorganizes the existing product widgets into pages.
        self._install_commercial_navigation()
        self._install_commercial_style()
        self.statusBar().showMessage("就绪 · v1.0.0 Final RC · 商业版分页界面")

    def _install_final_paired_timing_controls(self) -> None:
        params = self.waveform_channel_spin.parentWidget()
        layout = params.layout() if params is not None else None
        if not isinstance(layout, QFormLayout):
            raise RuntimeError("DSO-X parameter area must use QFormLayout")

        self.followup_position_edit = self._number_edit("0.484")
        self.followup_position_edit.setObjectName("followupPositionEdit")
        self.followup_scale_edit = self._number_edit("20e-9")
        self.followup_scale_edit.setObjectName("followupScaleEdit")
        layout.addRow("第二次 Position (s)", self.followup_position_edit)
        layout.addRow("第二次 Scale (s/div)", self.followup_scale_edit)

    def _install_recipe_debug_action(self) -> None:
        group = self.start_button.parentWidget()
        layout = group.layout()
        if not isinstance(layout, QGridLayout):
            raise RuntimeError("capture group must use QGridLayout")

        self.recipe_debug_button = QPushButton("工程调试 / 单步采集", group)
        self.recipe_debug_button.setObjectName("recipeDebugButton")
        note = QLabel(
            "8 步真机流程已验收；单步入口保留用于现场诊断，不影响一键正式采集。",
            group,
        )
        note.setObjectName("alphaNote")
        note.setWordWrap(True)
        layout.addWidget(QLabel("工程诊断"), 9, 0)
        layout.addWidget(self.recipe_debug_button, 9, 1, 1, 2)
        layout.addWidget(note, 9, 3, 1, 3)
        self.recipe_debug_button.clicked.connect(self._open_recipe_debugger)

    def _install_commercial_navigation(self) -> None:
        """Re-parent the mature product controls into focused commercial pages."""

        old_central = self.takeCentralWidget()
        if old_central is None:
            raise RuntimeError("main window central widget is missing")

        title = self.findChild(QLabel, "pageTitle")
        if title is None or title.parentWidget() is None:
            raise RuntimeError("product header is missing")
        header = title.parentWidget()

        fsw_group = self.fsw_resource_edit.parentWidget()
        dsox_group = self.dsox_resource_edit.parentWidget()
        capture_group = self.start_button.parentWidget()
        data_group = self.data_tree.parentWidget()
        log_group = self.log_view.parentWidget()
        if any(
            widget is None
            for widget in (fsw_group, dsox_group, capture_group, data_group, log_group)
        ):
            raise RuntimeError("one or more product groups could not be resolved")

        # Template/debug/log actions were historically embedded in unrelated
        # panels. Move the same live widgets rather than creating duplicate state.
        template_toolbar = self.template_combo.parentWidget()
        if template_toolbar is None:
            raise RuntimeError("template toolbar is missing")
        capture_layout = capture_group.layout()
        template_layout = template_toolbar.parentWidget().layout()
        if template_layout is not None:
            template_layout.removeWidget(template_toolbar)
        if capture_layout is not None:
            capture_layout.removeWidget(self.recipe_debug_button)

        data_layout = data_group.layout()
        if data_layout is not None:
            data_layout.removeWidget(self.open_session_log_button)

        # Hide the old row captions/notes that belonged to the former all-in-one
        # capture page. The functional widgets themselves are re-used below.
        for label in capture_group.findChildren(QLabel):
            text = label.text().strip()
            if text in {"实验配置模板", "工程诊断"}:
                label.hide()
            elif "8 步真机流程已验收" in text:
                label.hide()

        if isinstance(capture_group, QGroupBox):
            capture_group.setTitle("采集任务")
        if isinstance(fsw_group, QGroupBox):
            fsw_group.setTitle("频谱仪 · R&S FSW")
        if isinstance(dsox_group, QGroupBox):
            dsox_group.setTitle("示波器 · Keysight DSO-X 3034A")
        if isinstance(data_group, QGroupBox):
            data_group.setTitle("数据浏览与报告")
        if isinstance(log_group, QGroupBox):
            log_group.setTitle("运行日志")

        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)
        root.addWidget(header)
        root.addWidget(self._build_global_status_strip())

        body = QHBoxLayout()
        body.setSpacing(12)
        self.navigation_list = QListWidget(central)
        self.navigation_list.setObjectName("commercialNavigation")
        self.navigation_list.setFixedWidth(190)
        self.navigation_list.setSpacing(3)
        for title_text, _subtitle in _NAVIGATION_ITEMS:
            self.navigation_list.addItem(title_text)

        self.page_stack = QStackedWidget(central)
        self.page_stack.setObjectName("commercialPageStack")
        self.page_stack.addWidget(
            self._build_capture_page(capture_group)
        )
        self.page_stack.addWidget(
            self._build_instruments_page(fsw_group, dsox_group)
        )
        self.page_stack.addWidget(
            self._build_data_page(data_group)
        )
        self.page_stack.addWidget(
            self._build_templates_page(template_toolbar)
        )
        self.page_stack.addWidget(
            self._build_debug_page(self.recipe_debug_button)
        )
        self.page_stack.addWidget(
            self._build_logs_page(log_group, self.open_session_log_button)
        )

        body.addWidget(self.navigation_list)
        body.addWidget(self.page_stack, 1)
        root.addLayout(body, 1)
        self.setCentralWidget(central)

        self.navigation_list.currentRowChanged.connect(self._on_navigation_changed)
        self.navigation_list.setCurrentRow(0)

        self.resize(1380, 860)
        self.setMinimumSize(1080, 720)

        # Mirror the most important states while users move between pages.
        self._global_status_timer = QTimer(self)
        self._global_status_timer.setInterval(400)
        self._global_status_timer.timeout.connect(self._refresh_global_status)
        self._global_status_timer.start()
        self._refresh_global_status()

        old_central.deleteLater()

    def _build_global_status_strip(self) -> QWidget:
        frame = QFrame(self)
        frame.setObjectName("globalStatusStrip")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(8)

        label = QLabel("设备与任务状态")
        label.setObjectName("globalStatusTitle")
        self.global_fsw_status = QLabel()
        self.global_fsw_status.setObjectName("globalStatusPill")
        self.global_dsox_status = QLabel()
        self.global_dsox_status.setObjectName("globalStatusPill")
        self.global_job_status = QLabel()
        self.global_job_status.setObjectName("globalStatusPill")

        layout.addWidget(label)
        layout.addWidget(self.global_fsw_status)
        layout.addWidget(self.global_dsox_status)
        layout.addWidget(self.global_job_status)
        layout.addStretch(1)
        return frame

    def _build_page_frame(self, title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget(self.page_stack if hasattr(self, "page_stack") else self)
        page.setObjectName("commercialPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 2, 4, 4)
        layout.setSpacing(10)

        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        description = QLabel(subtitle)
        description.setObjectName("sectionSubtitle")
        description.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(description)
        return page, layout

    def _build_capture_page(self, capture_group: QWidget) -> QWidget:
        page, layout = self._build_page_frame(*_NAVIGATION_ITEMS[0])
        layout.addWidget(capture_group)
        layout.addStretch(1)
        return page

    def _build_instruments_page(self, fsw_group: QWidget, dsox_group: QWidget) -> QWidget:
        page, layout = self._build_page_frame(*_NAVIGATION_ITEMS[1])
        grid_host = QWidget(page)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.addWidget(fsw_group, 0, 0)
        grid.addWidget(dsox_group, 0, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addWidget(grid_host)
        layout.addStretch(1)
        return page

    def _build_data_page(self, data_group: QWidget) -> QWidget:
        page, layout = self._build_page_frame(*_NAVIGATION_ITEMS[2])
        layout.addWidget(data_group, 1)
        return page

    def _build_templates_page(self, toolbar: QWidget) -> QWidget:
        page, layout = self._build_page_frame(*_NAVIGATION_ITEMS[3])
        group = QGroupBox("实验配置模板", page)
        group_layout = QVBoxLayout(group)
        helper = QLabel(
            "将当前 VISA、Recipe、执行方式、频率与示波器参数保存为命名模板；"
            "加载模板后仍可在开始采集前继续修改。"
        )
        helper.setObjectName("mutedNote")
        helper.setWordWrap(True)
        group_layout.addWidget(helper)
        group_layout.addWidget(toolbar)
        layout.addWidget(group)
        layout.addStretch(1)
        return page

    def _build_debug_page(self, debug_button: QPushButton) -> QWidget:
        page, layout = self._build_page_frame(*_NAVIGATION_ITEMS[4])
        group = QGroupBox("现场工程诊断", page)
        group_layout = QVBoxLayout(group)
        warning = QLabel(
            "该入口面向研发、现场调试和售后定位。正常采集请使用“任务采集”页面。"
            "单步会话保持同一对 VISA Session，并允许逐步检查 Sweep Time、时间窗、"
            "FSW EXT ARM、两次 DSO-X Single 和最终 Free Run Single。"
        )
        warning.setObjectName("alphaNote")
        warning.setWordWrap(True)
        debug_button.setMinimumWidth(220)
        button_row = QHBoxLayout()
        button_row.addWidget(debug_button)
        button_row.addStretch(1)
        group_layout.addWidget(warning)
        group_layout.addLayout(button_row)
        layout.addWidget(group)
        layout.addStretch(1)
        return page

    def _build_logs_page(self, log_group: QWidget, open_log_button: QPushButton) -> QWidget:
        page, layout = self._build_page_frame(*_NAVIGATION_ITEMS[5])
        system_group = QGroupBox("系统信息", page)
        system_layout = QVBoxLayout(system_group)
        session_path = getattr(getattr(self, "_session_log", None), "path", "")
        info = QLabel(
            "采集参数会自动保存并在下次启动时恢复。\n"
            f"当前会话日志：{session_path}"
        )
        info.setObjectName("mutedNote")
        info.setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(open_log_button)
        row.addStretch(1)
        system_layout.addWidget(info)
        system_layout.addLayout(row)
        layout.addWidget(system_group)
        layout.addWidget(log_group, 1)
        return page

    def _on_navigation_changed(self, row: int) -> None:
        if row < 0 or row >= self.page_stack.count():
            return
        self.page_stack.setCurrentIndex(row)
        if row == 2:
            self._refresh_data_tree()
        elif row == 3 and hasattr(self, "_template_store"):
            self._refresh_template_list()

    def _refresh_global_status(self) -> None:
        if not hasattr(self, "global_fsw_status"):
            return
        self.global_fsw_status.setText(f"FSW · {self.fsw_status_label.text()}")
        self.global_dsox_status.setText(f"DSO-X · {self.dsox_status_label.text()}")
        self.global_job_status.setText(f"任务 · {self.job_state_label.text()}")

    def _install_commercial_style(self) -> None:
        self.setStyleSheet(
            self.styleSheet()
            + """
            QListWidget#commercialNavigation {
                background: #101828;
                color: #d0d5dd;
                border: 0;
                border-radius: 10px;
                padding: 8px;
                outline: 0;
                font-weight: 600;
            }
            QListWidget#commercialNavigation::item {
                border-radius: 7px;
                padding: 11px 12px;
                margin: 2px 0;
            }
            QListWidget#commercialNavigation::item:hover {
                background: #1d2939;
                color: white;
            }
            QListWidget#commercialNavigation::item:selected {
                background: #2f6fed;
                color: white;
            }
            QStackedWidget#commercialPageStack {
                background: transparent;
                border: 0;
            }
            QWidget#commercialPage {
                background: transparent;
            }
            QLabel#sectionTitle {
                color: #101828;
                font-size: 20px;
                font-weight: 700;
                padding: 2px 2px 0 2px;
            }
            QLabel#sectionSubtitle {
                color: #667085;
                font-size: 11px;
                padding: 0 2px 4px 2px;
            }
            QFrame#globalStatusStrip {
                background: white;
                border: 1px solid #e4e7ec;
                border-radius: 8px;
            }
            QLabel#globalStatusTitle {
                color: #475467;
                font-weight: 600;
                padding-right: 6px;
            }
            QLabel#globalStatusPill {
                background: #f2f4f7;
                color: #344054;
                border-radius: 9px;
                padding: 4px 9px;
                font-weight: 600;
            }
            QLabel#mutedNote {
                color: #667085;
                background: #f9fafb;
                border: 1px solid #eaecf0;
                border-radius: 6px;
                padding: 8px;
            }
            """
        )

    def _build_dsox_settings(self):
        settings = super()._build_dsox_settings()
        return replace(
            settings,
            followup_position_s=self._required_float(
                self.followup_position_edit,
                "第二次 Horizontal Position",
            ),
            followup_scale_s=self._required_float(
                self.followup_scale_edit,
                "第二次 Horizontal Scale",
            ),
        )

    def _sync_recipe_controls(self, *_args) -> None:
        super()._sync_recipe_controls(*_args)
        if not hasattr(self, "followup_position_edit"):
            return

        paired = self._selected_recipe() is CaptureRecipe.EXT_IMM_PAIR
        for widget in (self.followup_position_edit, self.followup_scale_edit):
            widget.setEnabled(paired and not self._capture_busy)
            widget.setVisible(paired)

        params = self.waveform_channel_spin.parentWidget()
        form = params.layout() if params is not None else None
        if isinstance(form, QFormLayout):
            for field in (self.followup_position_edit, self.followup_scale_edit):
                label = form.labelForField(field)
                if label is not None:
                    label.setVisible(paired)
            # DELAY/CYCLE timing remains relevant to the standalone DSO-X
            # recipe only; do not show those legacy business labels for paired.
            for field in (
                self.delay_timebase_scale_edit,
                self.cycle_timebase_scale_edit,
            ):
                field.setVisible(not paired)
                label = form.labelForField(field)
                if label is not None:
                    label.setVisible(not paired)

        self._update_recipe_summary()

    def _update_recipe_summary(self, *_args) -> None:
        if not hasattr(self, "recipe_combo"):
            return
        recipe = self._selected_recipe()
        channel = self.waveform_channel_spin.value()

        if recipe is CaptureRecipe.EXT_IMM_PAIR:
            position = (
                self.followup_position_edit.text().strip()
                if hasattr(self, "followup_position_edit")
                else "0.484"
            )
            scale = (
                self.followup_scale_edit.text().strip()
                if hasattr(self, "followup_scale_edit")
                else "20e-9"
            )
            mode = self._selected_execution_mode()
            mode_text = {
                ExecutionMode.SINGLE: "单次",
                ExecutionMode.FREQUENCY_SWEEP: "频率循环",
                ExecutionMode.FIXED_REPEAT: "固定频率重复",
            }[mode]
            self.recipe_summary_label.setText(
                f"{mode_text} · 读取 FSW Sweep Time T → DSO-X 第一次窗口 "
                f"Position=T/2、Scale=T/10 → FSW EXT Single ARM → "
                f"DSO-X CH{channel} Single #1，完成后读取/保存并触发 FSW → "
                f"读取 EXT Single 频谱 → 第二次 Position={position}s、Scale={scale}s/div → "
                "DSO-X Single #2，完成后读取/保存 → FSW Free Run Single。"
            )
            return

        # Preserve the standalone Recipe summaries from the Phase-8 base, but
        # make the customer Single requirement explicit to the operator.
        super()._update_recipe_summary(*_args)
        if recipe is CaptureRecipe.IMM_SPECTRUM_ONLY:
            self.recipe_summary_label.setText(
                "只连接 FSW · Trigger=IMM · 每个 Job 只执行一次 Single Sweep，完成后保存频谱。"
            )
        elif recipe is CaptureRecipe.DSOX_ONLY:
            delay_scale = self.delay_timebase_scale_edit.text().strip()
            cycle_scale = self.cycle_timebase_scale_edit.text().strip()
            self.recipe_summary_label.setText(
                f"只连接 DSO-X · CH{channel} · DELAY {delay_scale}s/div：Single 后保存；"
                f"CYCLE {cycle_scale}s/div：再次 Single 后保存。两次采集互相独立。"
            )

    def _set_capture_busy(self, busy: bool) -> None:
        super()._set_capture_busy(busy)
        if hasattr(self, "recipe_debug_button"):
            self.recipe_debug_button.setEnabled(
                not busy and self._recipe_debug_dialog is None
            )
        if hasattr(self, "_global_status_timer"):
            self._refresh_global_status()

    def _open_recipe_debugger(self) -> None:
        if self._capture_busy or self._recipe_debug_dialog is not None:
            return
        try:
            fsw_settings = self._build_fsw_settings()
            dsox_settings = self._build_dsox_settings()
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                "调试参数错误",
                f"请先确认两台仪表 VISA 地址及基础参数有效。\n\n{type(exc).__name__}: {exc}",
            )
            return

        dialog = RecipeDebugDialog(fsw_settings, dsox_settings, self)
        self._recipe_debug_dialog = dialog
        self.recipe_debug_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.fsw_connect_button.setEnabled(False)
        self.dsox_connect_button.setEnabled(False)
        dialog.finished.connect(self._on_recipe_debugger_closed)
        dialog.show()

    def _on_recipe_debugger_closed(self, _result: int) -> None:
        dialog = self._recipe_debug_dialog
        self._recipe_debug_dialog = None
        if dialog is not None:
            dialog.deleteLater()
        self._sync_recipe_controls()
        if hasattr(self, "recipe_debug_button"):
            self.recipe_debug_button.setEnabled(not self._capture_busy)
