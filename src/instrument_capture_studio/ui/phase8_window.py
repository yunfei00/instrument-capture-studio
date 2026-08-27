"""Phase 8 UI: separate capture recipe from repetition/execution mode."""

from dataclasses import replace

from PySide6.QtWidgets import QComboBox, QFormLayout, QGridLayout, QLabel

from instrument_capture_studio.app.capture_recipe import CaptureRecipe, ExecutionMode
from instrument_capture_studio.app.frequency_sweep import FrequencySweepPlan
from instrument_capture_studio.ui.final_window import MainWindow as FinalWindow


_RECIPE_TEXT = {
    "EXT联合 + IMM配对样本": CaptureRecipe.EXT_IMM_PAIR,
    "IMM频谱单采": CaptureRecipe.IMM_SPECTRUM_ONLY,
    "示波器单采": CaptureRecipe.DSOX_ONLY,
}


class MainWindow(FinalWindow):
    """Release-candidate window aligned to the real acquisition recipes."""

    def __init__(self) -> None:
        super().__init__()
        self._install_dsox_group_controls()
        self._install_recipe_controls()
        # New controls are installed after parent preference restoration, so
        # restore once more to apply their persisted values.
        self._preferences.restore(self)
        self.recipe_combo.currentTextChanged.connect(self._save_preferences)
        self.recipe_combo.currentTextChanged.connect(self._sync_recipe_controls)
        self.waveform_channel_spin.valueChanged.connect(self._update_recipe_summary)
        self.capture_mode_combo.currentIndexChanged.connect(self._update_recipe_summary)
        for edit in (
            self.delay_timebase_scale_edit,
            self.cycle_timebase_scale_edit,
        ):
            edit.editingFinished.connect(self._save_preferences)
            edit.textChanged.connect(self._update_recipe_summary)
        self._sync_recipe_controls()
        self._update_recipe_summary()
        self.statusBar().showMessage("就绪 · Phase 8A · Recipe RC")

    def _install_dsox_group_controls(self) -> None:
        params = self.waveform_channel_spin.parentWidget()
        layout = params.layout() if params is not None else None
        if not isinstance(layout, QFormLayout):
            raise RuntimeError("DSO-X parameter area must use QFormLayout")

        self.delay_timebase_scale_edit = self._number_edit("5e-7")
        self.delay_timebase_scale_edit.setObjectName("delayTimebaseScaleEdit")
        self.cycle_timebase_scale_edit = self._number_edit("1e-4")
        self.cycle_timebase_scale_edit.setObjectName("cycleTimebaseScaleEdit")

        layout.addRow("DELAY 数据时基 (s/div)", self.delay_timebase_scale_edit)
        layout.addRow("CYCLE 数据时基 (s/div)", self.cycle_timebase_scale_edit)

    def _install_recipe_controls(self) -> None:
        group = self.start_button.parentWidget()
        layout = group.layout()
        if not isinstance(layout, QGridLayout):
            raise RuntimeError("capture group must use QGridLayout")

        self.recipe_combo = QComboBox(group)
        self.recipe_combo.setObjectName("captureRecipeCombo")
        self.recipe_combo.addItems(list(_RECIPE_TEXT))
        self.recipe_summary_label = QLabel(group)
        self.recipe_summary_label.setObjectName("alphaNote")
        self.recipe_summary_label.setWordWrap(True)

        layout.addWidget(QLabel("采集内容"), 7, 0)
        layout.addWidget(self.recipe_combo, 7, 1, 1, 2)
        layout.addWidget(self.recipe_summary_label, 7, 3, 1, 3)

    def _selected_recipe(self) -> CaptureRecipe:
        return _RECIPE_TEXT[self.recipe_combo.currentText()]

    def _selected_execution_mode(self) -> ExecutionMode:
        index = self.capture_mode_combo.currentIndex()
        if index == 1:
            return ExecutionMode.FREQUENCY_SWEEP
        if index == 2:
            return ExecutionMode.FIXED_REPEAT
        return ExecutionMode.SINGLE

    def _sync_recipe_controls(self, *_args) -> None:
        recipe = self._selected_recipe()
        paired = recipe is CaptureRecipe.EXT_IMM_PAIR

        # Current Phase 8A exposes batch execution for the paired training
        # recipe first. Single-instrument batch modes will share the resumable
        # engine introduced in Phase 8B rather than creating a second engine.
        if not paired and self.capture_mode_combo.currentIndex() != 0:
            self.capture_mode_combo.setCurrentIndex(0)
        self.capture_mode_combo.setEnabled(paired and not self._capture_busy)

        requires_fsw = recipe in {
            CaptureRecipe.EXT_IMM_PAIR,
            CaptureRecipe.IMM_SPECTRUM_ONLY,
        }
        requires_dsox = recipe in {
            CaptureRecipe.EXT_IMM_PAIR,
            CaptureRecipe.DSOX_ONLY,
        }

        for widget in (
            self.fsw_resource_edit,
            self.center_hz_edit,
            self.span_hz_edit,
            self.rbw_hz_edit,
            self.vbw_hz_edit,
            self.fsw_timeout_edit,
            self.fsw_connect_button,
        ):
            widget.setEnabled(requires_fsw and not self._capture_busy)

        # Trigger is controlled by recipe: pair uses EXT then IMM; IMM-only
        # always uses IMM. Keep the legacy control visible but non-editable.
        self.trigger_source_combo.setEnabled(False)
        self.trigger_source_combo.setToolTip(
            "Phase 8 Recipe 自动控制 Trigger：配对样本 EXT→IMM；频谱单采固定 IMM。"
        )

        for widget in (
            self.dsox_resource_edit,
            self.delay_source1_edit,
            self.delay_source2_edit,
            self.delay_edge1_combo,
            self.delay_edge2_combo,
            self.cycle_source_edit,
            self.waveform_channel_spin,
            self.delay_timebase_scale_edit,
            self.cycle_timebase_scale_edit,
            self.dsox_connect_button,
        ):
            widget.setEnabled(requires_dsox and not self._capture_busy)

        self._sync_sweep_mode()
        self._update_recipe_summary()

    def _sync_sweep_mode(self, *_args) -> None:
        super()._sync_sweep_mode(*_args)
        if not hasattr(self, "recipe_combo"):
            return
        if self._selected_recipe() is not CaptureRecipe.EXT_IMM_PAIR:
            for widget in (
                self.sweep_start_mhz_edit,
                self.sweep_stop_mhz_edit,
                self.sweep_step_mhz_edit,
                self.sweep_span_mhz_edit,
                self.sweep_capture_count_spin,
                self.repeat_capture_count_spin,
            ):
                widget.setEnabled(False)

    def _build_dsox_settings(self):
        settings = super()._build_dsox_settings()
        return replace(
            settings,
            delay_timebase_scale_s=self._required_float(
                self.delay_timebase_scale_edit,
                "DELAY 数据时基",
            ),
            cycle_timebase_scale_s=self._required_float(
                self.cycle_timebase_scale_edit,
                "CYCLE 数据时基",
            ),
        )

    def _update_recipe_summary(self, *_args) -> None:
        if not hasattr(self, "recipe_combo"):
            return
        recipe = self._selected_recipe()
        channel = self.waveform_channel_spin.value()
        delay_scale = self.delay_timebase_scale_edit.text().strip()
        cycle_scale = self.cycle_timebase_scale_edit.text().strip()
        dsox_text = (
            f"DSO-X 两次独立采集：DELAY组 {delay_scale}s/div + "
            f"CYCLE组 {cycle_scale}s/div，均采 CH{channel}。"
        )
        if recipe is CaptureRecipe.EXT_IMM_PAIR:
            mode = self._selected_execution_mode()
            mode_text = {
                ExecutionMode.SINGLE: "单次",
                ExecutionMode.FREQUENCY_SWEEP: "频率循环",
                ExecutionMode.FIXED_REPEAT: "固定频率重复",
            }[mode]
            self.recipe_summary_label.setText(
                f"{mode_text} · FSW EXT先ARM → DELAY组采集并触发FSW → "
                f"读取EXT → CYCLE组第二次采集 → 同频点IMM。{dsox_text}"
            )
        elif recipe is CaptureRecipe.IMM_SPECTRUM_ONLY:
            self.recipe_summary_label.setText(
                "只连接 FSW · Trigger 固定 IMM · 每个 Job 保存 spectrum_imm。"
            )
        else:
            self.recipe_summary_label.setText(
                f"只连接 DSO-X。{dsox_text} 两组波形分别保存，不互相覆盖。"
            )

    def _start_capture(self) -> None:
        self._save_preferences()
        recipe = self._selected_recipe()
        execution = self._selected_execution_mode()

        try:
            fsw_settings = None
            dsox_settings = None
            if recipe in {CaptureRecipe.EXT_IMM_PAIR, CaptureRecipe.IMM_SPECTRUM_ONLY}:
                fsw_settings = self._build_fsw_settings()
            if recipe in {CaptureRecipe.EXT_IMM_PAIR, CaptureRecipe.DSOX_ONLY}:
                dsox_settings = self._build_dsox_settings()

            plan = None
            if recipe is CaptureRecipe.EXT_IMM_PAIR:
                if execution is ExecutionMode.FREQUENCY_SWEEP:
                    plan = self._build_sweep_plan()
                elif execution is ExecutionMode.FIXED_REPEAT:
                    center_hz = self._required_float(self.center_hz_edit, "中心频率")
                    span_hz = self._required_float(self.span_hz_edit, "Span")
                    plan = FrequencySweepPlan(
                        start_hz=center_hz,
                        stop_hz=center_hz,
                        step_hz=1.0,
                        span_hz=span_hz,
                        captures_per_frequency=self.repeat_capture_count_spin.value(),
                    )
            elif execution is not ExecutionMode.SINGLE:
                raise ValueError("IMM频谱单采和示波器单采当前请选择单次采集")
        except ValueError as exc:
            self._show_input_error(str(exc))
            return

        output_root = self.output_root_edit.text().strip()
        if not output_root:
            self._show_input_error("数据目录不能为空")
            return

        self._continuous_running = (
            recipe is CaptureRecipe.EXT_IMM_PAIR
            and execution is ExecutionMode.FIXED_REPEAT
        )
        self._sweep_running = (
            recipe is CaptureRecipe.EXT_IMM_PAIR
            and execution is not ExecutionMode.SINGLE
        )
        self._set_capture_busy(True)
        self.job_state_label.setText("RECIPE STARTING")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("正在启动采集 Recipe…")
        self._controller.start_recipe(
            {
                "recipe": recipe.value,
                "execution_mode": execution.value,
                "fsw_settings": fsw_settings,
                "dsox_settings": dsox_settings,
                "output_root": output_root,
                "plan": plan,
            }
        )
        self._append_log(
            f"Phase 8 Recipe：{recipe.value} · {execution.value} · "
            f"CH{self.waveform_channel_spin.value()} · "
            f"DELAY timebase={self.delay_timebase_scale_edit.text()} · "
            f"CYCLE timebase={self.cycle_timebase_scale_edit.text()}"
        )

    def _set_capture_busy(self, busy: bool) -> None:
        super()._set_capture_busy(busy)
        if hasattr(self, "recipe_combo"):
            self.recipe_combo.setEnabled(not busy)
            self._sync_recipe_controls()
