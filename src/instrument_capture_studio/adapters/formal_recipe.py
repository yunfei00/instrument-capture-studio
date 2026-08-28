"""Business-safe adapter primitives for the final paired acquisition recipe.

The operator prepares the FSW measurement on the front panel before a run.
These helpers deliberately preserve that measurement setup and only control the
pieces owned by the product recipe: Sweep Time readback, EXT/IMM trigger state,
and (for an explicit frequency-sweep execution mode) center/span changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from instrument_capture_studio.adapters.dsox3034a import (
    DSOX3034AAdapter,
    DSOX3034AConfig,
)
from instrument_capture_studio.adapters.fsw import FSWAdapter
from instrument_capture_studio.core.results import WaveformResult


CancelCheck = Callable[[], bool]


@dataclass(frozen=True)
class FormalDSOXConfig(DSOX3034AConfig):
    """Final paired-recipe DSO-X timing values."""

    followup_position_s: float = 0.484
    followup_scale_s: float = 20e-9

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.followup_position_s < 0:
            raise ValueError("followup_position_s must not be negative")
        if self.followup_scale_s <= 0:
            raise ValueError("followup_scale_s must be greater than 0")


class FormalFSWAdapter(FSWAdapter):
    """FSW primitives that do not overwrite the operator's measurement setup."""

    def read_sweep_time_s(self) -> float:
        value = float(self._driver.get_sweep_time())
        if value <= 0:
            raise ValueError(f"FSW returned invalid Sweep Time: {value}")
        return value

    def configure_frequency(
        self,
        center_frequency_hz: float,
        span_hz: float,
    ) -> None:
        """Apply an explicit sweep-plan frequency only when it changes the plan.

        Fixed-repeat builds its one-point plan from the same GUI center/span
        already stored in this adapter configuration. In that case this method
        intentionally does *not* write center/span to the FSW, preserving the
        operator's front-panel measurement setup. A real frequency sweep changes
        those plan values between points, so the required center/span writes are
        applied there.
        """
        center = float(center_frequency_hz)
        span = float(span_hz)
        if center < 0 or span < 0:
            raise ValueError("frequency plan values must not be negative")

        configured_center = self._config.center_frequency_hz
        configured_span = self._config.span_hz
        if configured_center == center and configured_span == span:
            return

        self._driver.set_center_frequency(center)
        self._driver.set_span(span)
        super().configure_frequency(center, span)

    def arm_external_current_setup(self) -> None:
        """Switch to EXT and arm once without touching center/span/RBW/VBW."""
        self._driver.set_trigger_source("EXT")
        self._driver.arm_trace_ascii(channel=self._config.channel)

    def acquire_freerun_current_setup(
        self,
        *,
        timeout_s: float | None = None,
        cancel_check: CancelCheck | None = None,
    ):
        """Switch to Free Run/IMM and acquire once without rewriting setup."""
        self._driver.set_trigger_source("IMM")
        trace = self._driver.acquire_trace_ascii(
            channel=self._config.channel,
            window=self._config.window,
            trace=self._config.trace,
            timeout_s=timeout_s,
            cancel_check=cancel_check,
        )
        return self._trace_to_result(trace, "IMM")


class FormalDSOXAdapter(DSOX3034AAdapter):
    """DSO-X timing-window primitives verified during staged hardware tests."""

    def configure_sync_window(self, sweep_time_s: float) -> dict[str, object]:
        sweep_time = float(sweep_time_s)
        if sweep_time <= 0:
            raise ValueError("sweep_time_s must be greater than 0")
        return self._configure_window(
            position_s=sweep_time / 2.0,
            scale_s_per_div=sweep_time / 10.0,
            window_kind="sync",
        )

    def configure_followup_window(self) -> dict[str, object]:
        config = self._config
        return self._configure_window(
            position_s=float(getattr(config, "followup_position_s", 0.484)),
            scale_s_per_div=float(getattr(config, "followup_scale_s", 20e-9)),
            window_kind="followup",
        )

    def acquire_sync_waveform(self) -> WaveformResult:
        return self._acquire_formal_waveform("sync")

    def acquire_followup_waveform(self) -> WaveformResult:
        return self._acquire_formal_waveform("followup")

    def _configure_window(
        self,
        *,
        position_s: float,
        scale_s_per_div: float,
        window_kind: str,
    ) -> dict[str, object]:
        if position_s < 0:
            raise ValueError("DSO-X Horizontal Position must not be negative")
        if scale_s_per_div <= 0:
            raise ValueError("DSO-X Horizontal Scale must be greater than 0")

        self._driver.write(":TIMebase:MODE MAIN")
        self._driver.write(":TIMebase:REFerence CENTer")
        self._driver.set_timebase_position(position_s)
        self._driver.set_timebase_scale(scale_s_per_div)

        mode = str(self._driver.query(":TIMebase:MODE?")).strip()
        reference = str(self._driver.query(":TIMebase:REFerence?")).strip()
        position_readback = float(self._driver.get_timebase_position())
        scale_readback = float(self._driver.get_timebase_scale())

        return {
            "window_kind": window_kind,
            "requested_position_s": position_s,
            "requested_scale_s_per_div": scale_s_per_div,
            "mode_readback": mode,
            "reference_readback": reference,
            "position_readback_s": position_readback,
            "scale_readback_s_per_div": scale_readback,
        }

    def _acquire_formal_waveform(self, sample_kind: str) -> WaveformResult:
        raw = self._driver.acquire_word_waveform(self._config.waveform_channel)
        result = self._convert_waveform(
            raw,
            sample_kind=sample_kind,
            timebase_scale_s=float(self._driver.get_timebase_scale()),
        )
        result.metadata["horizontal_position_s"] = float(
            self._driver.get_timebase_position()
        )
        return result
