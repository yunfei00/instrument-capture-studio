"""Final recipe-alignment window with retained engineering step debugger."""

from dataclasses import replace

from PySide6.QtWidgets import QFormLayout, QGridLayout, QLabel, QPushButton

from instrument_capture_studio.app.capture_recipe import CaptureRecipe, ExecutionMode
from instrument_capture_studio.ui.recipe_debug_dialog import RecipeDebugDialog
from instrument_capture_studio.ui.release_window import MainWindow as ReleaseWindow


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
        self.statusBar().showMessage("就绪 · v1.0.0 Final RC · Single 同步采集流程")

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

    def _build_fsw_settings(self):
        settings = super()._build_fsw_settings()
        if self._selected_recipe() is CaptureRecipe.EXT_IMM_PAIR:
            # The paired recipe intentionally preserves the FSW front-panel
            # measurement setup. Historical GUI fields defaulted RBW/VBW to
            # 1 MHz even though the paired workflow never applied them; keeping
            # those values in runtime configuration made metadata look as if the
            # instrument had been read back at 1 MHz. Actual RBW/VBW are queried
            # from the FSW separately before acquisition.
            return replace(settings, rbw_hz=None, vbw_hz=None)
        return settings

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
