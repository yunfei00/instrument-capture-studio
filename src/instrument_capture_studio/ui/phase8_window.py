"""Phase 8 UI: real capture recipes plus pause/resume Batch controls."""

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QPushButton,
)

from instrument_capture_studio.app.capture_recipe import CaptureRecipe, ExecutionMode
from instrument_capture_studio.app.frequency_sweep import FrequencySweepPlan
from instrument_capture_studio.app.resume import (
    ResumableBatch,
    find_latest_resumable_batch,
)
from instrument_capture_studio.ui.final_window import MainWindow as FinalWindow


_RECIPE_TEXT = {
    "EXT联合 + IMM配对样本": CaptureRecipe.EXT_IMM_PAIR,
    "IMM频谱单采": CaptureRecipe.IMM_SPECTRUM_ONLY,
    "示波器单采": CaptureRecipe.DSOX_ONLY,
}


class MainWindow(FinalWindow):
    """Release-candidate window aligned to the real acquisition recipes."""

    def __init__(self) -> None:
        self._batch_is_paused = False
        self._resumable_batch: ResumableBatch | None = None
        super().__init__()
        self._install_dsox_group_controls()
        self._install_recipe_controls()
        self._install_resume_controls()
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
        self.output_root_edit.editingFinished.connect(self._refresh_resumable_batch)
        self._controller.batch_pause_changed.connect(self._on_batch_pause_changed)
        self._sync_recipe_controls()
        self._update_recipe_summary()
        self._refresh_resumable_batch()
        self.statusBar().showMessage("就绪 · Phase 8B · Pause/Resume RC")

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

    def _install_resume_controls(self) -> None:
        group = self.start_button.parentWidget()
        layout = group.layout()
        if not isinstance(layout, QGridLayout):
            raise RuntimeError("capture group must use QGridLayout")

        self.pause_button = QPushButton("暂停采集", group)
        self.pause_button.setObjectName("pauseCaptureButton")
        self.pause_button.setEnabled(False)
        self.resume_previous_button = QPushButton("继续上次任务", group)
        self.resume_previous_button.setObjectName("resumePreviousBatchButton")
        self.resume_previous_button.setEnabled(False)
        self.resume_summary_label = QLabel("暂无可继续的未完成 Batch", group)
        self.resume_summary_label.setObjectName("alphaNote")
        self.resume_summary_label.setWordWrap(True)

        layout.addWidget(QLabel("批量任务"), 8, 0)
        layout.addWidget(self.pause_button, 8, 1)
        layout.addWidget(self.resume_previous_button, 8, 2)
        layout.addWidget(self.resume_summary_label, 8, 3, 1, 3)

        self.pause_button.clicked.connect(self._toggle_pause)
        self.resume_previous_button.clicked.connect(self._resume_previous_batch)

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
        self._update_pause_controls()

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
        if hasattr(self, "pause_button"):
            self._update_pause_controls()

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
        self._start_recipe_request(resume_batch=None)

    def _start_recipe_request(self, resume_batch: ResumableBatch | None) -> None:
        self._save_preferences()
        recipe = self._selected_recipe()
        execution = self._selected_execution_mode()

        if resume_batch is not None:
            recipe = CaptureRecipe.EXT_IMM_PAIR
            execution = self._execution_for_resume(resume_batch)

        try:
            fsw_settings = None
            dsox_settings = None
            if recipe in {CaptureRecipe.EXT_IMM_PAIR, CaptureRecipe.IMM_SPECTRUM_ONLY}:
                fsw_settings = self._build_fsw_settings()
            if recipe in {CaptureRecipe.EXT_IMM_PAIR, CaptureRecipe.DSOX_ONLY}:
                dsox_settings = self._build_dsox_settings()

            plan = resume_batch.plan if resume_batch is not None else None
            if recipe is CaptureRecipe.EXT_IMM_PAIR and plan is None:
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
            elif recipe is not CaptureRecipe.EXT_IMM_PAIR and execution is not ExecutionMode.SINGLE:
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
        self._batch_is_paused = False
        self._set_capture_busy(True)
        self.job_state_label.setText(
            "BATCH RESUMING" if resume_batch is not None else "RECIPE STARTING"
        )
        self.progress_bar.setRange(0, 100)
        if resume_batch is None:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("正在启动采集 Recipe…")
        else:
            percent = int(
                round(
                    resume_batch.completed_captures
                    * 100
                    / max(1, resume_batch.total_captures)
                )
            )
            self.progress_bar.setValue(percent)
            self.progress_bar.setFormat(
                f"继续任务 · {resume_batch.completed_captures}/"
                f"{resume_batch.total_captures}"
            )

        self._controller.start_recipe(
            {
                "recipe": recipe.value,
                "execution_mode": execution.value,
                "fsw_settings": fsw_settings,
                "dsox_settings": dsox_settings,
                "output_root": output_root,
                "plan": plan,
                "resume_manifest_path": (
                    str(resume_batch.manifest_path)
                    if resume_batch is not None
                    else None
                ),
            }
        )
        action = "继续" if resume_batch is not None else "开始"
        self._append_log(
            f"{action} Phase 8 Recipe：{recipe.value} · {execution.value} · "
            f"CH{self.waveform_channel_spin.value()} · "
            f"DELAY timebase={self.delay_timebase_scale_edit.text()} · "
            f"CYCLE timebase={self.cycle_timebase_scale_edit.text()}"
        )

    @staticmethod
    def _execution_for_resume(batch: ResumableBatch) -> ExecutionMode:
        if batch.plan.frequency_count == 1 and batch.plan.captures_per_frequency > 1:
            return ExecutionMode.FIXED_REPEAT
        return ExecutionMode.FREQUENCY_SWEEP

    def _apply_resume_plan_to_controls(self, batch: ResumableBatch) -> None:
        plan = batch.plan
        self.recipe_combo.setCurrentText("EXT联合 + IMM配对样本")
        execution = self._execution_for_resume(batch)
        if execution is ExecutionMode.FIXED_REPEAT:
            self.capture_mode_combo.setCurrentIndex(2)
            self.center_hz_edit.setText(f"{plan.start_hz:g}")
            self.span_hz_edit.setText(f"{plan.span_hz:g}")
            self.repeat_capture_count_spin.setValue(plan.captures_per_frequency)
        else:
            self.capture_mode_combo.setCurrentIndex(1)
            self.sweep_start_mhz_edit.setText(f"{plan.start_hz / 1e6:g}")
            self.sweep_stop_mhz_edit.setText(f"{plan.stop_hz / 1e6:g}")
            self.sweep_step_mhz_edit.setText(f"{plan.step_hz / 1e6:g}")
            self.sweep_span_mhz_edit.setText(f"{plan.span_hz / 1e6:g}")
            self.sweep_capture_count_spin.setValue(plan.captures_per_frequency)
        self._update_sweep_summary()
        self._update_recipe_summary()

    def _refresh_resumable_batch(self, *_args) -> None:
        if not hasattr(self, "resume_previous_button"):
            return
        root_text = self.output_root_edit.text().strip()
        batch = None
        if root_text:
            try:
                batch = find_latest_resumable_batch(Path(root_text))
            except OSError:
                batch = None
        self._resumable_batch = batch

        if batch is None:
            self.resume_summary_label.setText("暂无可继续的未完成 Batch")
        else:
            self.resume_summary_label.setText(
                f"{batch.batch_id} · {batch.state.upper()} · "
                f"已完成 {batch.completed_captures}/{batch.total_captures} · "
                f"剩余 {batch.remaining_captures}"
            )
        self.resume_previous_button.setEnabled(
            batch is not None and not self._capture_busy
        )

    def _resume_previous_batch(self) -> None:
        batch = self._resumable_batch
        if batch is None or self._capture_busy:
            self._refresh_resumable_batch()
            return
        self._apply_resume_plan_to_controls(batch)
        self._start_recipe_request(resume_batch=batch)

    def _toggle_pause(self) -> None:
        if not self._capture_busy or not self._sweep_running:
            return
        if self._batch_is_paused:
            self.job_state_label.setText("RESUMING")
            self.pause_button.setText("正在继续…")
            self.pause_button.setEnabled(False)
            self._controller.resume_capture()
            return

        self.job_state_label.setText("PAUSE REQUESTED")
        self.pause_button.setText("等待样本完成…")
        self.pause_button.setEnabled(False)
        self.statusBar().showMessage("已请求暂停；当前完整逻辑样本结束后暂停。")
        self._controller.pause_capture()

    def _on_batch_pause_changed(
        self,
        paused: bool,
        batch_id: str,
        completed: int,
        total: int,
    ) -> None:
        self._batch_is_paused = paused
        if paused:
            self.job_state_label.setText("PAUSED")
            self.pause_button.setText("继续采集")
            self.progress_bar.setFormat(f"PAUSED · {completed}/{total}")
            self.statusBar().showMessage(
                f"Batch 已暂停 · {batch_id} · {completed}/{total}"
            )
            self._append_log(
                f"Batch 已在完整逻辑样本边界暂停：{completed}/{total}"
            )
        else:
            self.job_state_label.setText("BATCH RUNNING")
            self.pause_button.setText("暂停采集")
            self.statusBar().showMessage(
                f"Batch 已继续 · {batch_id} · {completed}/{total}"
            )
            self._append_log(
                f"Batch 继续采集：从 {completed + 1}/{total} 开始"
            )
        self._update_pause_controls()

    def _update_pause_controls(self) -> None:
        if not hasattr(self, "pause_button"):
            return
        batch_mode = False
        if hasattr(self, "recipe_combo"):
            batch_mode = (
                self._selected_recipe() is CaptureRecipe.EXT_IMM_PAIR
                and self._selected_execution_mode() is not ExecutionMode.SINGLE
            )
        self.pause_button.setEnabled(self._capture_busy and batch_mode)
        if not self._capture_busy:
            self._batch_is_paused = False
            self.pause_button.setText("暂停采集")
        if hasattr(self, "resume_previous_button"):
            self.resume_previous_button.setEnabled(
                self._resumable_batch is not None and not self._capture_busy
            )

    def _choose_output_root(self) -> None:
        super()._choose_output_root()
        self._refresh_resumable_batch()

    def _on_batch_finished(self, result) -> None:
        self._batch_is_paused = False
        super()._on_batch_finished(result)
        self.pause_button.setText("暂停采集")
        self._refresh_resumable_batch()

    def _set_capture_busy(self, busy: bool) -> None:
        super()._set_capture_busy(busy)
        if hasattr(self, "recipe_combo"):
            self.recipe_combo.setEnabled(not busy)
            self._sync_recipe_controls()
        if hasattr(self, "pause_button"):
            self._update_pause_controls()
        if hasattr(self, "resume_previous_button") and not busy:
            self._refresh_resumable_batch()
