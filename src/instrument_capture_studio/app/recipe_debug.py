"""Stateful single-step hardware qualification for the new paired recipe.

This module deliberately does not modify the production paired workflow yet.
It drives the already-available platform drivers one verified SCPI step at a
time so the real FSW + DSO-X timing sequence can be qualified on hardware
before it is promoted into the formal Schema-v1 replacement workflow.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable


CancelCheck = Callable[[], bool]


class RecipeDebugState(str, Enum):
    IDLE = "idle"
    CONNECTED = "connected"
    SWEEP_TIME_READ = "sweep_time_read"
    SYNC_SCOPE_CONFIGURED = "sync_scope_configured"
    FSW_ARMED = "fsw_armed"
    SYNC_SCOPE_CAPTURED = "sync_scope_captured"
    EXT_SPECTRUM_READ = "ext_spectrum_read"
    FOLLOWUP_SCOPE_CONFIGURED = "followup_scope_configured"
    FOLLOWUP_SCOPE_CAPTURED = "followup_scope_captured"
    COMPLETE = "complete"
    CLOSED = "closed"


class RecipeDebugSession:
    """Keep both VISA sessions open while the operator advances one step at a time."""

    def __init__(
        self,
        fsw_driver: Any,
        dsox_driver: Any,
        *,
        fsw_timeout_s: float,
        cancel_check: CancelCheck | None = None,
    ) -> None:
        if fsw_timeout_s <= 0:
            raise ValueError("fsw_timeout_s must be greater than 0")
        self.fsw = fsw_driver
        self.dsox = dsox_driver
        self.fsw_timeout_s = float(fsw_timeout_s)
        self.cancel_check = cancel_check
        self.state = RecipeDebugState.IDLE
        self.sweep_time_s: float | None = None
        self.waveform_sync: Any | None = None
        self.spectrum_ext: Any | None = None
        self.waveform_followup: Any | None = None
        self.spectrum_freerun: Any | None = None

    def connect(self) -> dict[str, object]:
        self._require(RecipeDebugState.IDLE)
        fsw_identity = self.fsw.connect()
        try:
            dsox_identity = self.dsox.connect()
        except Exception:
            try:
                self.fsw.disconnect()
            finally:
                raise
        self.state = RecipeDebugState.CONNECTED
        return {
            "state": self.state.value,
            "fsw_model": getattr(fsw_identity, "model", ""),
            "dsox_model": getattr(dsox_identity, "model", ""),
        }

    def read_sweep_time(self) -> dict[str, object]:
        self._require(RecipeDebugState.CONNECTED)
        sweep_time_s = float(self.fsw.get_sweep_time())
        if sweep_time_s <= 0:
            raise ValueError(f"FSW returned invalid sweep time: {sweep_time_s}")
        self.sweep_time_s = sweep_time_s
        self.state = RecipeDebugState.SWEEP_TIME_READ
        return {
            "state": self.state.value,
            "scpi": "SENSe:SWEep:TIME?",
            "sweep_time_s": sweep_time_s,
            "sync_position_s": sweep_time_s / 2.0,
            "sync_scale_s_per_div": sweep_time_s / 10.0,
        }

    def configure_sync_scope(self) -> dict[str, object]:
        self._require(RecipeDebugState.SWEEP_TIME_READ)
        if self.sweep_time_s is None:
            raise RuntimeError("FSW sweep time has not been read")
        payload = self._configure_scope_window(
            position_s=self.sweep_time_s / 2.0,
            scale_s_per_div=self.sweep_time_s / 10.0,
        )
        self.state = RecipeDebugState.SYNC_SCOPE_CONFIGURED
        payload["state"] = self.state.value
        return payload

    def arm_fsw_ext(self) -> dict[str, object]:
        self._require(RecipeDebugState.SYNC_SCOPE_CONFIGURED)
        # Do not apply center/span/RBW/VBW here. The operator intentionally
        # prepares the FSW measurement and Sweep Time on the front panel before
        # starting the recipe. This step changes Trigger only, then arms once.
        self.fsw.set_trigger_source("EXT")
        self.fsw.arm_trace_ascii(channel=1)
        self.state = RecipeDebugState.FSW_ARMED
        return {
            "state": self.state.value,
            "scpi": [
                "TRIGger:SEQuence:SOURce EXT",
                "INITiate1:CONTinuous OFF",
                "FORMat:DATA ASCii",
                "INITiate1:IMMediate",
            ],
            "message": "FSW armed and waiting for EXT trigger",
        }

    def capture_sync_scope(self, channel: int) -> dict[str, object]:
        self._require(RecipeDebugState.FSW_ARMED)
        waveform = self.dsox.acquire_word_waveform(channel)
        self.waveform_sync = waveform
        self.state = RecipeDebugState.SYNC_SCOPE_CAPTURED
        return {
            "state": self.state.value,
            "scpi": f":DIGitize CHANnel{channel} + waveform read",
            "channel": channel,
            "points": len(waveform.raw_samples),
            "x_increment_s": waveform.preamble.x_increment,
        }

    def read_ext_spectrum(self) -> dict[str, object]:
        self._require(RecipeDebugState.SYNC_SCOPE_CAPTURED)
        spectrum = self.fsw.wait_and_read_trace_ascii(
            timeout_s=self.fsw_timeout_s,
            cancel_check=self.cancel_check,
        )
        self.spectrum_ext = spectrum
        self.state = RecipeDebugState.EXT_SPECTRUM_READ
        return {
            "state": self.state.value,
            "scpi": "*OPC / *ESR? polling + TRACe1:DATA? TRACE1",
            "points": len(spectrum.levels),
            "start_hz": spectrum.start_hz,
            "stop_hz": spectrum.stop_hz,
        }

    def configure_followup_scope(
        self,
        *,
        position_s: float,
        scale_s_per_div: float,
    ) -> dict[str, object]:
        self._require(RecipeDebugState.EXT_SPECTRUM_READ)
        payload = self._configure_scope_window(
            position_s=position_s,
            scale_s_per_div=scale_s_per_div,
        )
        self.state = RecipeDebugState.FOLLOWUP_SCOPE_CONFIGURED
        payload["state"] = self.state.value
        return payload

    def capture_followup_scope(self, channel: int) -> dict[str, object]:
        self._require(RecipeDebugState.FOLLOWUP_SCOPE_CONFIGURED)
        waveform = self.dsox.acquire_word_waveform(channel)
        self.waveform_followup = waveform
        self.state = RecipeDebugState.FOLLOWUP_SCOPE_CAPTURED
        return {
            "state": self.state.value,
            "scpi": f":DIGitize CHANnel{channel} + waveform read",
            "channel": channel,
            "points": len(waveform.raw_samples),
            "x_increment_s": waveform.preamble.x_increment,
        }

    def capture_freerun_spectrum(self) -> dict[str, object]:
        self._require(RecipeDebugState.FOLLOWUP_SCOPE_CAPTURED)
        # Free Run on FSW is IMMediate. As with the EXT arm, preserve the
        # operator's current measurement configuration and only change Trigger.
        self.fsw.set_trigger_source("IMM")
        spectrum = self.fsw.acquire_trace_ascii(
            channel=1,
            window=1,
            trace=1,
            timeout_s=self.fsw_timeout_s,
            cancel_check=self.cancel_check,
        )
        self.spectrum_freerun = spectrum
        self.state = RecipeDebugState.COMPLETE
        return {
            "state": self.state.value,
            "scpi": [
                "TRIGger:SEQuence:SOURce IMM",
                "INITiate1:IMMediate",
                "TRACe1:DATA? TRACE1",
            ],
            "points": len(spectrum.levels),
            "start_hz": spectrum.start_hz,
            "stop_hz": spectrum.stop_hz,
        }

    def reset(self) -> dict[str, object]:
        errors: list[str] = []
        if self.state is RecipeDebugState.CLOSED:
            return {"state": self.state.value, "errors": errors}

        try:
            self.fsw.abort()
        except Exception as exc:
            errors.append(f"FSW ABORt: {type(exc).__name__}: {exc}")
        try:
            self.fsw.set_trigger_source("IMM")
        except Exception as exc:
            errors.append(f"FSW Free Run: {type(exc).__name__}: {exc}")
        try:
            self.dsox.abort()
        except Exception as exc:
            errors.append(f"DSO-X STOP: {type(exc).__name__}: {exc}")
        try:
            self.dsox.disconnect()
        except Exception as exc:
            errors.append(f"DSO-X disconnect: {type(exc).__name__}: {exc}")
        try:
            self.fsw.disconnect()
        except Exception as exc:
            errors.append(f"FSW disconnect: {type(exc).__name__}: {exc}")

        self.state = RecipeDebugState.CLOSED
        return {"state": self.state.value, "errors": errors}

    def _configure_scope_window(
        self,
        *,
        position_s: float,
        scale_s_per_div: float,
    ) -> dict[str, object]:
        if position_s < 0:
            raise ValueError("DSO-X Horizontal Position must not be negative")
        if scale_s_per_div <= 0:
            raise ValueError("DSO-X Horizontal Scale must be greater than 0")

        # MODE / REFERENCE are available through the platform driver's generic
        # SCPI primitives. Position / Scale already have typed platform APIs.
        self.dsox.write(":TIMebase:MODE MAIN")
        self.dsox.write(":TIMebase:REFerence CENTer")
        self.dsox.set_timebase_position(float(position_s))
        self.dsox.set_timebase_scale(float(scale_s_per_div))

        mode = str(self.dsox.query(":TIMebase:MODE?")).strip()
        reference = str(self.dsox.query(":TIMebase:REFerence?")).strip()
        position_readback_s = float(self.dsox.get_timebase_position())
        scale_readback_s = float(self.dsox.get_timebase_scale())

        return {
            "scpi": [
                ":TIMebase:MODE MAIN",
                ":TIMebase:REFerence CENTer",
                f":TIMebase:POSition {position_s:g}",
                f":TIMebase:SCALe {scale_s_per_div:g}",
                ":TIMebase:MODE?",
                ":TIMebase:REFerence?",
                ":TIMebase:POSition?",
                ":TIMebase:SCALe?",
            ],
            "requested_position_s": float(position_s),
            "requested_scale_s_per_div": float(scale_s_per_div),
            "mode_readback": mode,
            "reference_readback": reference,
            "position_readback_s": position_readback_s,
            "scale_readback_s_per_div": scale_readback_s,
        }

    def _require(self, expected: RecipeDebugState) -> None:
        if self.state is not expected:
            raise RuntimeError(
                f"debug step requires state={expected.value}, current={self.state.value}"
            )
