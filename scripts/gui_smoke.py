"""Offscreen smoke test for the released desktop shell."""

from PySide6.QtWidgets import QLabel

from instrument_capture_studio.ui.app import create_application, create_main_window


def main() -> None:
    app = create_application([])
    window = create_main_window()

    assert window.windowTitle() == "Instrument Capture Studio"
    assert type(window).__module__.endswith("snapshot_window")
    assert window.safe_close_pending is False
    assert window.connection_tests_active == 0

    assert window.capture_mode_combo.count() == 3
    assert window.capture_mode_combo.findText("固定频率连续采集") >= 0
    assert window.recipe_combo.count() == 3
    assert window.recipe_combo.findText("EXT联合 + IMM配对样本") >= 0
    assert window.recipe_combo.findText("IMM频谱单采") >= 0
    assert window.recipe_combo.findText("示波器单采") >= 0
    assert window.waveform_channel_spin.minimum() == 1
    assert window.waveform_channel_spin.maximum() == 4

    assert window.pause_button.text() == "暂停采集"
    assert hasattr(window, "resume_previous_button")
    assert hasattr(window, "resume_summary_label")
    assert hasattr(window, "template_combo")
    assert hasattr(window, "batch_report_button")
    assert hasattr(window, "batch_trace_export_button")
    assert window.recipe_debug_button.text() == "工程调试 / 单步采集"
    assert hasattr(window, "followup_position_edit")
    assert hasattr(window, "followup_scale_edit")

    assert window.commercial_nav.count() == 6
    assert window.commercial_nav.item(0).text() == "任务采集"
    assert window.commercial_nav.item(1).text() == "仪表连接"
    assert window.commercial_nav.item(2).text() == "数据与报告"
    assert window.commercial_stack.count() == 6
    assert window.commercial_task_parameter_card.title() == "任务关键参数"
    assert window.commercial_task_control_card.title() == "任务控制与状态"
    assert window.commercial_task_summary_card.title() == "本次配置摘要"

    assert window.auto_pause_checkbox.isChecked()
    assert window.auto_pause_minutes_spin.value() == 55
    assert hasattr(window, "capture_time_estimate_label")
    assert hasattr(window, "capture_runtime_label")

    assert hasattr(window, "data_search_edit")
    assert window.data_search_edit.placeholderText()
    assert hasattr(window, "data_status_filter")
    assert window.data_status_filter.count() == 3
    assert window.data_status_filter.itemText(0) == "全部状态"
    assert hasattr(window, "data_filter_refresh_button")
    assert hasattr(window, "manual_review_button")
    assert window.manual_review_button.text() == "人工筛选当前 Batch"
    assert hasattr(window, "directory_review_button")
    assert window.directory_review_button.text() == "选择目录人工筛选"
    assert hasattr(window, "project_record_button")
    assert window.project_record_button.text() == "编辑 10 项…"
    assert hasattr(window, "project_record_summary")
    assert hasattr(window, "edit_data_records_button")
    assert window.edit_data_records_button.text() == "编辑项目记录"
    assert hasattr(window, "directory_records_button")
    assert window.directory_records_button.text() == "目录项目记录"
    assert hasattr(window, "snapshot_all_checkbox")
    assert "Snapshot All" in window.snapshot_all_checkbox.text()
    assert not window.snapshot_all_checkbox.isChecked()

    assert hasattr(window, "fsw_workspace_hint")
    assert hasattr(window, "dsox_workspace_hint")
    assert hasattr(window, "data_empty_hint")
    assert hasattr(window, "fsw_identity_label")
    assert hasattr(window, "dsox_identity_label")
    assert window.capture_mode_caption.text() == "执行方式"

    footer = window.findChild(QLabel, "sidebarFooter")
    assert footer is not None and footer.isHidden()
    assert window.start_button.parentWidget().objectName() == "taskActionBar"
    assert (
        window.start_button.parentWidget().parentWidget()
        is window.commercial_task_control_card
    )
    assert window.recipe_summary_label.parentWidget() is window.commercial_task_summary_card

    window.recipe_combo.setCurrentText("EXT联合 + IMM配对样本")
    window.capture_mode_combo.setCurrentText("单次采集")
    window._sync_recipe_controls()
    window._refresh_quick_status()
    assert window.sweep_start_mhz_edit.parentWidget().isHidden()
    assert window.repeat_capture_count_spin.isHidden()
    assert window.followup_position_edit.isVisibleTo(window.commercial_task_parameter_card)
    assert not window.center_hz_edit.isVisibleTo(window.commercial_task_parameter_card)
    assert not window.rbw_hz_edit.parentWidget().isHidden()
    assert window.delay_source1_edit.parentWidget().isHidden()
    assert window.task_summary_recipe.text() == "EXT联合 + IMM配对样本"
    assert "FSW" in window.task_summary_frequency.text()
    assert not window.auto_pause_checkbox.isEnabled()
    assert window.snapshot_all_checkbox.isEnabled()

    window.snapshot_all_checkbox.setChecked(True)
    window._update_recipe_summary()
    assert "EXT 读取" in window.recipe_summary_label.text()
    assert "Snapshot All：开启" in window.recipe_summary_label.text()
    window._set_instrument_identity(
        "fsw",
        {
            "model": "FSW",
            "serial_number": "SN1",
            "firmware_version": "FW1",
            "address": "TCPIP::1",
        },
    )
    assert "型号 FSW" in window.fsw_identity_label.text()
    assert "SN1" in window.fsw_identity_label.text()

    window.recipe_combo.setCurrentText("IMM频谱单采")
    window._sync_recipe_controls()
    assert not window.snapshot_all_checkbox.isEnabled()
    window.recipe_combo.setCurrentText("EXT联合 + IMM配对样本")
    window._sync_recipe_controls()

    window.capture_mode_combo.setCurrentText("频率循环采集")
    window._sync_sweep_mode()
    assert not window.sweep_start_mhz_edit.parentWidget().isHidden()
    assert window.repeat_capture_count_spin.isHidden()
    assert window.auto_pause_checkbox.isEnabled()
    assert "完整逻辑样本" in window.capture_time_estimate_label.text()

    window.capture_mode_combo.setCurrentText("固定频率连续采集")
    window._sync_sweep_mode()
    window._refresh_quick_status()
    assert window.sweep_start_mhz_edit.parentWidget().isHidden()
    assert not window.repeat_capture_count_spin.isHidden()
    assert window.center_hz_edit.isVisibleTo(window.commercial_task_parameter_card)
    assert "连续" in window.task_summary_frequency.text()

    badge = window.findChild(QLabel, "alphaBadge")
    assert badge is not None and badge.text() == "v1.2.0"
    assert badge.maximumWidth() == 118

    window._controller.shutdown()
    window.deleteLater()
    app.processEvents()
    print("Instrument Capture Studio v1.2.0 Snapshot-All GUI smoke test PASS")


if __name__ == "__main__":
    main()
