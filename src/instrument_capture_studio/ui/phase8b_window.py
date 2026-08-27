"""Phase 8B hardening: freeze and restore the exact Batch runtime settings."""

from __future__ import annotations

from pathlib import Path

from instrument_capture_studio.app.batch_configuration import (
    BatchCaptureConfiguration,
    batch_configuration_path,
    write_batch_configuration,
)
from instrument_capture_studio.app.capture_recipe import CaptureRecipe, ExecutionMode
from instrument_capture_studio.app.resume import ResumableBatch
from instrument_capture_studio.ui.phase8_window import MainWindow as Phase8MainWindow


class MainWindow(Phase8MainWindow):
    """Phase 8B window with configuration-safe pause/restart resume."""

    def __init__(self) -> None:
        self._resume_runtime_configuration: BatchCaptureConfiguration | None = None
        self._pending_batch_configuration: BatchCaptureConfiguration | None = None
        self._pending_batch_output_root: Path | None = None
        super().__init__()
        self._controller.batch_started.connect(self._persist_started_batch_configuration)
        self.statusBar().showMessage("就绪 · Phase 8B · Frozen Resume Settings RC")

    def _build_fsw_settings(self):
        if self._resume_runtime_configuration is not None:
            return self._resume_runtime_configuration.fsw_settings
        return super()._build_fsw_settings()

    def _build_dsox_settings(self):
        if self._resume_runtime_configuration is not None:
            return self._resume_runtime_configuration.dsox_settings
        return super()._build_dsox_settings()

    @staticmethod
    def _execution_for_resume(batch: ResumableBatch) -> ExecutionMode:
        return batch.configuration.execution_mode

    def _start_recipe_request(self, resume_batch: ResumableBatch | None) -> None:
        self._resume_runtime_configuration = (
            resume_batch.configuration if resume_batch is not None else None
        )
        self._pending_batch_configuration = None
        self._pending_batch_output_root = None

        try:
            recipe = (
                resume_batch.configuration.recipe
                if resume_batch is not None
                else self._selected_recipe()
            )
            execution = (
                resume_batch.configuration.execution_mode
                if resume_batch is not None
                else self._selected_execution_mode()
            )

            if (
                recipe is CaptureRecipe.EXT_IMM_PAIR
                and execution is not ExecutionMode.SINGLE
            ):
                # Build before starting the worker so the snapshot represents
                # the exact settings that the request will use. On resume these
                # methods return the frozen dataclasses rather than QSettings.
                configuration = BatchCaptureConfiguration(
                    recipe=recipe,
                    execution_mode=execution,
                    fsw_settings=self._build_fsw_settings(),
                    dsox_settings=self._build_dsox_settings(),
                )
                output_text = self.output_root_edit.text().strip()
                if output_text:
                    self._pending_batch_configuration = configuration
                    self._pending_batch_output_root = Path(output_text).expanduser()

            super()._start_recipe_request(resume_batch)
        finally:
            # The request already contains immutable runtime dataclasses, so the
            # override is only needed while the request is being constructed.
            self._resume_runtime_configuration = None

    def _persist_started_batch_configuration(
        self,
        batch_id: str,
        _total_captures: int,
    ) -> None:
        configuration = self._pending_batch_configuration
        output_root = self._pending_batch_output_root
        if configuration is None or output_root is None:
            return

        path = batch_configuration_path(output_root, batch_id)
        try:
            write_batch_configuration(path, configuration)
        except Exception as exc:
            self._append_log(
                "保存 Batch 参数快照失败："
                f"{type(exc).__name__}: {exc}"
            )
            # Do not silently claim crash-resume safety when the snapshot could
            # not be persisted. Stop at the next cooperative boundary.
            self._controller.cancel_capture()
            self.statusBar().showMessage("Batch 参数快照保存失败，已请求安全停止", 10000)
            return

        self._append_log(
            "Batch 参数已冻结："
            f"{batch_id} · CH{configuration.dsox_settings.waveform_channel} · "
            f"DELAY {configuration.dsox_settings.delay_timebase_scale_s:g}s/div · "
            f"CYCLE {configuration.dsox_settings.cycle_timebase_scale_s:g}s/div"
        )
        self._pending_batch_configuration = None
        self._pending_batch_output_root = None

    def _apply_resume_plan_to_controls(self, batch: ResumableBatch) -> None:
        super()._apply_resume_plan_to_controls(batch)
        config = batch.configuration
        fsw = config.fsw_settings
        dsox = config.dsox_settings

        self.fsw_resource_edit.setText(fsw.resource)
        if fsw.center_frequency_hz is not None:
            self.center_hz_edit.setText(f"{fsw.center_frequency_hz:g}")
        if fsw.span_hz is not None:
            self.span_hz_edit.setText(f"{fsw.span_hz:g}")
        if fsw.rbw_hz is not None:
            self.rbw_hz_edit.setText(f"{fsw.rbw_hz:g}")
        if fsw.vbw_hz is not None:
            self.vbw_hz_edit.setText(f"{fsw.vbw_hz:g}")
        self.fsw_timeout_edit.setText(f"{fsw.step_timeout_s:g}")
        if fsw.trigger_source:
            index = self.trigger_source_combo.findText(str(fsw.trigger_source))
            if index >= 0:
                self.trigger_source_combo.setCurrentIndex(index)

        self.dsox_resource_edit.setText(dsox.resource)
        self.delay_source1_edit.setText(dsox.delay_source1)
        self.delay_source2_edit.setText(dsox.delay_source2)
        edge1 = self.delay_edge1_combo.findText(dsox.delay_edge1)
        edge2 = self.delay_edge2_combo.findText(dsox.delay_edge2)
        if edge1 >= 0:
            self.delay_edge1_combo.setCurrentIndex(edge1)
        if edge2 >= 0:
            self.delay_edge2_combo.setCurrentIndex(edge2)
        self.cycle_source_edit.setText(dsox.cycle_count_source)
        self.waveform_channel_spin.setValue(dsox.waveform_channel)
        self.delay_timebase_scale_edit.setText(f"{dsox.delay_timebase_scale_s:g}")
        self.cycle_timebase_scale_edit.setText(f"{dsox.cycle_timebase_scale_s:g}")

        self._update_sweep_summary()
        self._update_recipe_summary()
        self._append_log(
            "已从 Batch 快照恢复原采集参数；继续任务不会使用当前临时 GUI 参数。"
        )

    def _refresh_resumable_batch(self, *_args) -> None:
        super()._refresh_resumable_batch(*_args)
        batch = self._resumable_batch
        if batch is None:
            return
        config = batch.configuration
        dsox = config.dsox_settings
        self.resume_summary_label.setText(
            self.resume_summary_label.text()
            + f" · 原参数 CH{dsox.waveform_channel}"
            + f" · DELAY {dsox.delay_timebase_scale_s:g}s/div"
            + f" · CYCLE {dsox.cycle_timebase_scale_s:g}s/div"
        )
