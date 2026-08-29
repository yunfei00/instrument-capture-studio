"""Second-stage commercial workspace polish based on real desktop screenshots.

This layer keeps the qualified acquisition widgets and signal wiring untouched.
It focuses on reducing mode-irrelevant controls, fixing sidebar/header visual
artifacts on macOS/Windows, and making the secondary pages look intentional
instead of unfinished when little data is available.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
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
from instrument_capture_studio.ui.polished_window import MainWindow as PolishedWindow


class MainWindow(PolishedWindow):
    """Commercial Final-RC workspace refined against real screenshots."""

    def __init__(self) -> None:
        self._workspace_polish_ready = False
        super().__init__()
        self._install_workspace_refinement()
        self._workspace_polish_ready = True
        self._refresh_workspace_mode_visibility()
        self._refresh_data_empty_hint()
        self._apply_workspace_style()
        self.statusBar().showMessage("就绪")

    # ------------------------------------------------------------------
    # Hooks that preserve parent behavior and add presentation-only sync
    # ------------------------------------------------------------------
    def _sync_recipe_controls(self, *_args) -> None:
        super()._sync_recipe_controls(*_args)
        if self._workspace_polish_ready:
            self._refresh_workspace_mode_visibility()

    def _sync_sweep_mode(self, *_args) -> None:
        super()._sync_sweep_mode(*_args)
        if self._workspace_polish_ready:
            self._refresh_workspace_mode_visibility()

    def _refresh_data_tree(self) -> None:
        super()._refresh_data_tree()
        if self._workspace_polish_ready:
            self._refresh_data_empty_hint()

    # ------------------------------------------------------------------
    # Workspace installation
    # ------------------------------------------------------------------
    def _install_workspace_refinement(self) -> None:
        self._polish_sidebar_branding()
        self._polish_task_labels()
        self._install_instrument_guidance()
        self._install_data_empty_guidance()
        self._install_secondary_page_guides()

    def _polish_sidebar_branding(self) -> None:
        sidebar = self.findChild(QFrame, "commercialSidebar")
        if sidebar is not None:
            sidebar.setFixedWidth(180)

        title = self.findChild(QLabel, "sidebarTitle")
        if title is not None:
            title.setText("工作区")

        subtitle = self.findChild(QLabel, "sidebarSubtitle")
        if subtitle is not None:
            subtitle.setText("采集工作台")

        footer = self.findChild(QLabel, "sidebarFooter")
        if footer is not None:
            # Version already has a dedicated badge in the product header.
            footer.hide()

    def _polish_task_labels(self) -> None:
        if hasattr(self, "task_channel_label"):
            self.task_channel_label.setText("示波器通道")
        if hasattr(self, "task_followup_position_label"):
            self.task_followup_position_label.setText("第二次水平位置 (s)")
        if hasattr(self, "task_followup_scale_label"):
            self.task_followup_scale_label.setText("第二次水平时基 (s/div)")

    def _install_instrument_guidance(self) -> None:
        fsw_group = self.fsw_resource_edit.parentWidget()
        dsox_group = self.dsox_resource_edit.parentWidget()

        self.fsw_workspace_hint = QLabel()
        self.fsw_workspace_hint.setObjectName("instrumentWorkspaceHint")
        self.fsw_workspace_hint.setWordWrap(True)

        self.dsox_workspace_hint = QLabel()
        self.dsox_workspace_hint.setObjectName("instrumentWorkspaceHint")
        self.dsox_workspace_hint.setWordWrap(True)

        for group, hint in (
            (fsw_group, self.fsw_workspace_hint),
            (dsox_group, self.dsox_workspace_hint),
        ):
            layout = group.layout() if group is not None else None
            if isinstance(layout, QFormLayout):
                layout.addRow(hint)
            elif isinstance(layout, QVBoxLayout):
                layout.addWidget(hint)

        body = self._page_body_layout(1)
        if body is not None:
            self._remove_trailing_stretch(body)
            body.addWidget(
                self._build_guide_card(
                    "连接建议",
                    (
                        (
                            "1  填写 VISA 地址",
                            "支持 TCPIP / USB VISA 资源字符串；常用地址会随本机偏好保存。",
                        ),
                        (
                            "2  分别测试连接",
                            "先确认 FSW、DSO-X 状态均可用，再进入正式任务采集。",
                        ),
                        (
                            "3  保持长连接",
                            "Batch 内复用连接，减少频繁重连对连续采集稳定性的影响。",
                        ),
                    ),
                )
            )
            body.addStretch(1)

    def _install_data_empty_guidance(self) -> None:
        self.data_empty_hint = QLabel(
            "当前数据目录暂无可浏览的 Batch / Job。完成一次采集后，结果会自动出现在下方列表。"
        )
        self.data_empty_hint.setObjectName("dataEmptyHint")
        self.data_empty_hint.setWordWrap(True)

        group = self.data_tree.parentWidget()
        layout = group.layout() if group is not None else None
        if isinstance(layout, QVBoxLayout):
            index = layout.indexOf(self.data_tree)
            if index < 0:
                layout.addWidget(self.data_empty_hint)
            else:
                layout.insertWidget(index, self.data_empty_hint)

    def _install_secondary_page_guides(self) -> None:
        template_body = self._page_body_layout(3)
        if template_body is not None:
            self._remove_trailing_stretch(template_body)
            template_body.addWidget(
                self._build_guide_card(
                    "推荐使用流程",
                    (
                        (
                            "保存",
                            "先在任务采集和仪表连接页完成一次真实配置，再输入模板名称并保存。",
                        ),
                        (
                            "加载",
                            "下次实验选择已有模板并加载，地址、Recipe、频率计划与输出目录会一起恢复。",
                        ),
                        (
                            "维护",
                            "参数变更后可用同名模板重新保存；过期方案及时删除，避免现场误用。",
                        ),
                    ),
                )
            )
            template_body.addStretch(1)

        debug_body = self._page_body_layout(4)
        if debug_body is not None:
            self._remove_trailing_stretch(debug_body)
            debug_body.addWidget(
                self._build_guide_card(
                    "什么时候使用工程调试",
                    (
                        (
                            "链路验证",
                            "确认 Sweep Time、EXT ARM、Single/STOP 等关键同步步骤是否按预期执行。",
                        ),
                        (
                            "现场定位",
                            "正式任务失败时逐步执行采集 Recipe，定位具体仪表或具体步骤。",
                        ),
                        (
                            "结果复核",
                            "结合设置与日志页查看会话日志，保留可复现的现场诊断证据。",
                        ),
                    ),
                )
            )
            debug_body.addStretch(1)

    # ------------------------------------------------------------------
    # Dynamic visibility / guidance
    # ------------------------------------------------------------------
    def _refresh_workspace_mode_visibility(self) -> None:
        recipe = self._selected_recipe()
        mode = self._selected_execution_mode()

        sweep_widget = self.sweep_start_mhz_edit.parentWidget()
        show_sweep = (
            recipe is not CaptureRecipe.DSOX_ONLY
            and mode is ExecutionMode.FREQUENCY_SWEEP
        )
        if sweep_widget is not None:
            sweep_widget.setVisible(show_sweep)

        capture_group = self.capture_mode_combo.parentWidget()
        capture_layout = capture_group.layout() if capture_group is not None else None
        show_repeat = (
            recipe is not CaptureRecipe.DSOX_ONLY
            and mode is ExecutionMode.FIXED_REPEAT
        )
        if isinstance(capture_layout, QGridLayout):
            self._set_grid_row_visible(capture_layout, 6, show_repeat)

        self._refresh_instrument_guidance(recipe, mode)

    def _refresh_instrument_guidance(
        self,
        recipe: CaptureRecipe,
        mode: ExecutionMode,
    ) -> None:
        if not hasattr(self, "fsw_workspace_hint"):
            return

        if recipe is CaptureRecipe.EXT_IMM_PAIR:
            if mode is ExecutionMode.SINGLE:
                fsw_text = (
                    "联合单采：Center/Span 与 Sweep Time 以 FSW 当前测量设置为准；"
                    "软件读取 Sweep Time 后完成两次 DSO-X Single 同步。"
                )
            elif mode is ExecutionMode.FREQUENCY_SWEEP:
                fsw_text = (
                    "频率循环：频率计划来自任务采集页；RBW/VBW 与 Step Timeout 在这里统一管理。"
                )
            else:
                fsw_text = (
                    "固定频率连续：Center/Span 与连续次数来自任务采集页；Batch 内保持长连接。"
                )
            dsox_text = (
                "联合 Recipe 下无需配置 DELAY/CYCLE 旧参数。第一次窗口由 FSW Sweep Time 自动计算；"
                "第二次水平位置与时基在任务采集页设置。"
            )
        elif recipe is CaptureRecipe.IMM_SPECTRUM_ONLY:
            fsw_text = "当前 Recipe 仅使用 FSW；执行一次 IMM / Free Run Single Sweep 后保存频谱。"
            dsox_text = "当前 Recipe 不使用 DSO-X；地址可以保留，切换回联合或示波器单采时继续使用。"
        else:
            fsw_text = "当前 Recipe 不使用 FSW；地址可以保留，切换回联合或频谱单采时继续使用。"
            dsox_text = "示波器单采：DELAY/CYCLE 相关参数在本页显示，并分别执行独立 Single 采集。"

        self.fsw_workspace_hint.setText(fsw_text)
        self.dsox_workspace_hint.setText(dsox_text)

    def _refresh_data_empty_hint(self) -> None:
        if not hasattr(self, "data_empty_hint"):
            return
        empty = self.data_tree.topLevelItemCount() == 0
        if not empty:
            first = self.data_tree.topLevelItem(0)
            empty = first is not None and first.text(0) == "暂无数据"
        self.data_empty_hint.setVisible(empty)

    @staticmethod
    def _set_grid_row_visible(layout: QGridLayout, row: int, visible: bool) -> None:
        for column in range(layout.columnCount()):
            item = layout.itemAtPosition(row, column)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setVisible(visible)

    def _page_body_layout(self, index: int) -> QVBoxLayout | None:
        page = self.commercial_stack.widget(index)
        if page is None:
            return None
        scroll = page.findChild(QScrollArea, "commercialScrollArea")
        body = scroll.widget() if scroll is not None else None
        layout = body.layout() if body is not None else None
        return layout if isinstance(layout, QVBoxLayout) else None

    @staticmethod
    def _remove_trailing_stretch(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.itemAt(layout.count() - 1)
            if item is None or item.spacerItem() is None:
                break
            layout.takeAt(layout.count() - 1)

    @staticmethod
    def _build_guide_card(
        title: str,
        items: tuple[tuple[str, str], ...],
    ) -> QGroupBox:
        card = QGroupBox(title)
        card.setObjectName("workspaceGuideCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 18, 14, 14)
        row.setSpacing(10)

        for heading, description in items:
            tile = QFrame(card)
            tile.setObjectName("workspaceGuideTile")
            layout = QVBoxLayout(tile)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(5)
            heading_label = QLabel(heading, tile)
            heading_label.setObjectName("workspaceGuideTitle")
            body_label = QLabel(description, tile)
            body_label.setObjectName("workspaceGuideText")
            body_label.setWordWrap(True)
            layout.addWidget(heading_label)
            layout.addWidget(body_label)
            layout.addStretch(1)
            row.addWidget(tile, 1)
        return card

    # ------------------------------------------------------------------
    # Cross-platform visual cleanup
    # ------------------------------------------------------------------
    def _apply_workspace_style(self) -> None:
        self.setStyleSheet(
            self.styleSheet()
            + """
            QFrame#commercialSidebar {
                background: #1d2a3a;
                border: none;
                border-radius: 10px;
            }
            QLabel#sidebarTitle,
            QLabel#sidebarSubtitle,
            QLabel#sidebarFooter {
                background: transparent;
                border: none;
                padding: 0;
            }
            QLabel#sidebarTitle {
                color: #ffffff;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#sidebarSubtitle {
                color: #9fb0c3;
                font-size: 11px;
            }
            QListWidget#commercialNav::item {
                min-height: 42px;
                padding-left: 12px;
            }
            QLabel#alphaBadge {
                min-width: 138px;
                max-width: 138px;
                min-height: 42px;
                max-height: 42px;
                border-radius: 8px;
                font-weight: 700;
            }
            QLabel#instrumentWorkspaceHint {
                background: #f8fafc;
                color: #667085;
                border: 1px solid #e4e9ef;
                border-radius: 6px;
                padding: 9px 10px;
                font-size: 12px;
            }
            QLabel#dataEmptyHint {
                background: #eff6ff;
                color: #315b8a;
                border: 1px solid #cfe0f5;
                border-radius: 7px;
                padding: 10px 12px;
            }
            QGroupBox#workspaceGuideCard {
                background: #ffffff;
                border: 1px solid #d8e0e8;
                border-radius: 9px;
                margin-top: 10px;
                font-weight: 650;
            }
            QGroupBox#workspaceGuideCard::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
            }
            QFrame#workspaceGuideTile {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 7px;
            }
            QLabel#workspaceGuideTitle {
                color: #263548;
                font-weight: 700;
            }
            QLabel#workspaceGuideText {
                color: #667085;
                font-size: 12px;
            }
            QStatusBar {
                color: #667085;
                font-size: 12px;
            }
            """
        )
