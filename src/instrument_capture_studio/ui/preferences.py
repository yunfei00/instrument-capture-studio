"""Persistent desktop preferences for the capture station UI."""

from PySide6.QtCore import QSettings


class WindowPreferences:
    """Save, restore, export, and apply capture-window parameter values."""

    _LINE_EDITS = {
        "fsw/resource": "fsw_resource_edit",
        "fsw/center_hz": "center_hz_edit",
        "fsw/span_hz": "span_hz_edit",
        "fsw/rbw_hz": "rbw_hz_edit",
        "fsw/vbw_hz": "vbw_hz_edit",
        "fsw/step_timeout_s": "fsw_timeout_edit",
        "dsox/resource": "dsox_resource_edit",
        "dsox/delay_source1": "delay_source1_edit",
        "dsox/delay_source2": "delay_source2_edit",
        "dsox/cycle_source": "cycle_source_edit",
        "dsox/delay_timebase_scale_s": "delay_timebase_scale_edit",
        "dsox/cycle_timebase_scale_s": "cycle_timebase_scale_edit",
        "dsox/followup_position_s": "followup_position_edit",
        "dsox/followup_scale_s": "followup_scale_edit",
        "capture/output_root": "output_root_edit",
        "sweep/start_mhz": "sweep_start_mhz_edit",
        "sweep/stop_mhz": "sweep_stop_mhz_edit",
        "sweep/step_mhz": "sweep_step_mhz_edit",
        "sweep/span_mhz": "sweep_span_mhz_edit",
    }

    _COMBOS = {
        "fsw/trigger_source": "trigger_source_combo",
        "dsox/delay_edge1": "delay_edge1_combo",
        "dsox/delay_edge2": "delay_edge2_combo",
        "capture/mode": "capture_mode_combo",
        "capture/recipe": "recipe_combo",
    }

    _SPINS = {
        "dsox/waveform_channel": "waveform_channel_spin",
        "sweep/captures_per_frequency": "sweep_capture_count_spin",
        "continuous/captures": "repeat_capture_count_spin",
        "long_session/auto_pause_minutes": "auto_pause_minutes_spin",
    }

    _CHECKBOXES = {
        "long_session/auto_pause_enabled": "auto_pause_checkbox",
        "dsox/snapshot_all_enabled": "snapshot_all_checkbox",
    }

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings(
            "InstrumentCaptureStudio",
            "InstrumentCaptureStudio",
        )

    def snapshot(self, window) -> dict[str, object]:
        values: dict[str, object] = {}
        for key, attribute in self._LINE_EDITS.items():
            if hasattr(window, attribute):
                values[key] = getattr(window, attribute).text()
        for key, attribute in self._COMBOS.items():
            if hasattr(window, attribute):
                values[key] = getattr(window, attribute).currentText()
        for key, attribute in self._SPINS.items():
            if hasattr(window, attribute):
                values[key] = getattr(window, attribute).value()
        for key, attribute in self._CHECKBOXES.items():
            if hasattr(window, attribute):
                values[key] = getattr(window, attribute).isChecked()
        return values

    def apply(self, window, values: dict[str, object]) -> None:
        for key, attribute in self._LINE_EDITS.items():
            if key not in values or not hasattr(window, attribute):
                continue
            getattr(window, attribute).setText(str(values[key]))
        for key, attribute in self._COMBOS.items():
            if key not in values or not hasattr(window, attribute):
                continue
            widget = getattr(window, attribute)
            value = str(values[key])
            index = widget.findText(value)
            if index >= 0:
                widget.setCurrentIndex(index)
        for key, attribute in self._SPINS.items():
            if key not in values or not hasattr(window, attribute):
                continue
            try:
                getattr(window, attribute).setValue(int(values[key]))
            except (TypeError, ValueError):
                continue
        for key, attribute in self._CHECKBOXES.items():
            if key not in values or not hasattr(window, attribute):
                continue
            raw = values[key]
            if isinstance(raw, str):
                checked = raw.strip().lower() in {"1", "true", "yes", "on"}
            else:
                checked = bool(raw)
            getattr(window, attribute).setChecked(checked)

    def restore(self, window) -> None:
        values: dict[str, object] = {}
        for key in (
            *self._LINE_EDITS,
            *self._COMBOS,
            *self._SPINS,
            *self._CHECKBOXES,
        ):
            if self._settings.contains(key):
                values[key] = self._settings.value(key)
        self.apply(window, values)

    def save(self, window) -> None:
        for key, value in self.snapshot(window).items():
            self._settings.setValue(key, value)
        self._settings.sync()
