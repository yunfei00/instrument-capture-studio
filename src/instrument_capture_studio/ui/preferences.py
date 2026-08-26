"""Persistent desktop preferences for the capture station UI."""

from PySide6.QtCore import QSettings


class WindowPreferences:
    """Save and restore the last values entered in the main capture window."""

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
        "capture/output_root": "output_root_edit",
    }

    _COMBOS = {
        "fsw/trigger_source": "trigger_source_combo",
        "dsox/delay_edge1": "delay_edge1_combo",
        "dsox/delay_edge2": "delay_edge2_combo",
    }

    _SPINS = {
        "dsox/waveform_channel": "waveform_channel_spin",
    }

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings(
            "InstrumentCaptureStudio",
            "InstrumentCaptureStudio",
        )

    def restore(self, window) -> None:
        for key, attribute in self._LINE_EDITS.items():
            if not self._settings.contains(key):
                continue
            widget = getattr(window, attribute)
            widget.setText(str(self._settings.value(key, "")))

        for key, attribute in self._COMBOS.items():
            if not self._settings.contains(key):
                continue
            widget = getattr(window, attribute)
            value = str(self._settings.value(key, ""))
            index = widget.findText(value)
            if index >= 0:
                widget.setCurrentIndex(index)

        for key, attribute in self._SPINS.items():
            if not self._settings.contains(key):
                continue
            widget = getattr(window, attribute)
            try:
                widget.setValue(int(self._settings.value(key)))
            except (TypeError, ValueError):
                continue

    def save(self, window) -> None:
        for key, attribute in self._LINE_EDITS.items():
            widget = getattr(window, attribute)
            self._settings.setValue(key, widget.text())

        for key, attribute in self._COMBOS.items():
            widget = getattr(window, attribute)
            self._settings.setValue(key, widget.currentText())

        for key, attribute in self._SPINS.items():
            widget = getattr(window, attribute)
            self._settings.setValue(key, widget.value())

        self._settings.sync()
