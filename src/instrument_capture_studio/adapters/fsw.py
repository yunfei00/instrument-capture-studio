from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from typing import Any, Protocol

from instrument_capture_studio.adapters.driver_guard import DriverErrorGuard
from instrument_capture_studio.adapters.interfaces import SpectrumAnalyzerAdapter
from instrument_capture_studio.core.models import InstrumentState, InstrumentStatus
from instrument_capture_studio.core.results import SpectrumResult


class FSWDriverProtocol(Protocol):
    """FSW 商业 Adapter 所依赖的底层 Driver 能力。"""

    @property
    def is_connected(self) -> bool: ...

    @property
    def state(self) -> Any: ...

    @property
    def identity(self) -> Any: ...

    def connect(self) -> Any: ...
    def disconnect(self) -> None: ...
    def set_center_frequency(self, value_hz: float) -> None: ...
    def set_span(self, value_hz: float) -> None: ...
    def set_rbw(self, value_hz: float) -> None: ...
    def set_vbw(self, value_hz: float) -> None: ...
    def set_trigger_source(self, source: str) -> None: ...

    def arm_trace_ascii(self, *, channel: int = 1) -> None: ...

    def wait_and_read_trace_ascii(
        self,
        *,
        window: int = 1,
        trace: int = 1,
        timeout_s: float | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Any: ...

    def acquire_trace_ascii(
        self,
        *,
        channel: int = 1,
        window: int = 1,
        trace: int = 1,
        timeout_s: float | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Any: ...


@dataclass(frozen=True)
class FSWConfig:
    """FSW 商业采集配置。"""

    center_frequency_hz: float | None = None
    span_hz: float | None = None
    rbw_hz: float | None = None
    vbw_hz: float | None = None
    trigger_source: str | None = None
    channel: int = 1
    window: int = 1
    trace: int = 1


class FSWAdapter(SpectrumAnalyzerAdapter):
    """Rohde & Schwarz FSW 商业产品适配器。"""

    def __init__(
        self,
        address: str,
        driver: FSWDriverProtocol,
        config: FSWConfig | None = None,
    ):
        super().__init__(name="FSW", address=address)
        self._driver = DriverErrorGuard(driver)
        self._config = config or FSWConfig()

    def get_configuration(self) -> dict[str, object]:
        return dict(asdict(self._config))

    def configure_frequency(
        self,
        center_frequency_hz: float,
        span_hz: float,
    ) -> None:
        center_frequency_hz = float(center_frequency_hz)
        span_hz = float(span_hz)
        if center_frequency_hz < 0:
            raise ValueError("center_frequency_hz must not be negative")
        if span_hz < 0:
            raise ValueError("span_hz must not be negative")
        self._config = replace(
            self._config,
            center_frequency_hz=center_frequency_hz,
            span_hz=span_hz,
        )

    def connect(self) -> None:
        self._driver.connect()

    def disconnect(self) -> None:
        self._driver.disconnect()

    def is_connected(self) -> bool:
        return bool(self._driver.is_connected)

    def get_status(self) -> InstrumentStatus:
        identity = self._driver.identity
        return InstrumentStatus(
            name=self.name,
            address=self.address,
            state=self._map_state(),
            model=getattr(identity, "model", None) if identity is not None else None,
            serial_number=(
                getattr(identity, "serial_number", None)
                if identity is not None
                else None
            ),
            firmware_version=(
                getattr(identity, "firmware", None)
                if identity is not None
                else None
            ),
        )

    def acquire_spectrum(
        self,
        *,
        timeout_s: float | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> SpectrumResult:
        return self.acquire_spectrum_with_trigger(
            None,
            timeout_s=timeout_s,
            cancel_check=cancel_check,
        )

    def acquire_spectrum_with_trigger(
        self,
        trigger_source: str | None,
        *,
        timeout_s: float | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> SpectrumResult:
        """Acquire one trace, optionally overriding only this acquisition's trigger."""
        self._apply_configuration(trigger_source_override=trigger_source)
        config = self._config
        trace = self._driver.acquire_trace_ascii(
            channel=config.channel,
            window=config.window,
            trace=config.trace,
            timeout_s=timeout_s,
            cancel_check=cancel_check,
        )
        return self._trace_to_result(trace, trigger_source)

    def arm_spectrum(self, trigger_source: str = "EXT") -> None:
        """Configure and arm FSW, returning before the external trigger arrives.

        Newer platform drivers expose ``arm_trace_ascii`` directly. During the
        Phase-8 transition some Windows machines can still have an older
        instrument-automation-platform checkout. That driver already exposes
        the lower-level primitives, so use them instead of crashing with a raw
        AttributeError.
        """
        self._apply_configuration(trigger_source_override=trigger_source)
        config = self._config
        if self._driver.supports("arm_trace_ascii"):
            self._driver.arm_trace_ascii(channel=config.channel)
            return

        self._driver.set_continuous(False, channel=config.channel)
        self._driver.set_trace_ascii()
        self._driver.initiate(channel=config.channel)

    def read_armed_spectrum(
        self,
        *,
        timeout_s: float | None = None,
        cancel_check: Callable[[], bool] | None = None,
        trigger_source: str = "EXT",
    ) -> SpectrumResult:
        """Wait for and read the trace started by :meth:`arm_spectrum`."""
        config = self._config
        if self._driver.supports("wait_and_read_trace_ascii"):
            trace = self._driver.wait_and_read_trace_ascii(
                window=config.window,
                trace=config.trace,
                timeout_s=timeout_s,
                cancel_check=cancel_check,
            )
            return self._trace_to_result(trace, trigger_source)

        # Compatibility path for a platform checkout made before the split
        # ARM / WAIT / READ convenience methods were added.
        if timeout_s is None and cancel_check is None:
            if not self._driver.wait_operation_complete():
                raise RuntimeError("FSW measurement did not complete")
        else:
            self._driver.wait_operation_complete_bounded(
                timeout_s,
                cancel_check=cancel_check,
            )

        start_hz = float(self._driver.get_start_frequency())
        stop_hz = float(self._driver.get_stop_frequency())
        levels = tuple(
            self._driver.read_trace_ascii(
                window=config.window,
                trace=config.trace,
            )
        )
        return self._raw_trace_to_result(
            levels,
            start_hz=start_hz,
            stop_hz=stop_hz,
            trigger_source=trigger_source,
        )

    def _raw_trace_to_result(
        self,
        levels: tuple[float, ...],
        *,
        start_hz: float,
        stop_hz: float,
        trigger_source: str | None,
    ) -> SpectrumResult:
        points = len(levels)
        if points <= 1:
            frequencies_hz = [start_hz] if points == 1 else []
        else:
            increment_hz = (stop_hz - start_hz) / (points - 1)
            frequencies_hz = [
                start_hz + index * increment_hz
                for index in range(points)
            ]
        config = self._config
        return SpectrumResult(
            frequencies_hz=frequencies_hz,
            amplitudes_dbm=list(levels),
            metadata={
                "start_hz": start_hz,
                "stop_hz": stop_hz,
                "channel": config.channel,
                "window": config.window,
                "trace": config.trace,
                "trigger_source": trigger_source or config.trigger_source,
                "transfer_format": "ASCII",
            },
        )

    def _trace_to_result(
        self,
        trace: Any,
        trigger_source: str | None,
    ) -> SpectrumResult:
        config = self._config
        effective_trigger = trigger_source or config.trigger_source
        return SpectrumResult(
            frequencies_hz=list(trace.frequencies_hz),
            amplitudes_dbm=list(trace.levels),
            metadata={
                "start_hz": trace.start_hz,
                "stop_hz": trace.stop_hz,
                "channel": config.channel,
                "window": config.window,
                "trace": config.trace,
                "trigger_source": effective_trigger,
                "transfer_format": "ASCII",
            },
        )

    def _apply_configuration(
        self,
        *,
        trigger_source_override: str | None = None,
    ) -> None:
        config = self._config
        if config.center_frequency_hz is not None:
            self._driver.set_center_frequency(config.center_frequency_hz)
        if config.span_hz is not None:
            self._driver.set_span(config.span_hz)
        if config.rbw_hz is not None:
            self._driver.set_rbw(config.rbw_hz)
        if config.vbw_hz is not None:
            self._driver.set_vbw(config.vbw_hz)

        trigger_source = (
            trigger_source_override
            if trigger_source_override is not None
            else config.trigger_source
        )
        if trigger_source is not None:
            self._driver.set_trigger_source(trigger_source)

    def _map_state(self) -> InstrumentState:
        raw_state = self._driver.state
        value = getattr(raw_state, "value", str(raw_state))
        mapping = {
            "disconnected": InstrumentState.DISCONNECTED,
            "connecting": InstrumentState.CONNECTING,
            "connected": InstrumentState.CONNECTED,
            "ready": InstrumentState.CONNECTED,
            "busy": InstrumentState.BUSY,
            "recovering": InstrumentState.CONNECTING,
            "error": InstrumentState.ERROR,
        }
        return mapping.get(str(value).lower(), InstrumentState.ERROR)
