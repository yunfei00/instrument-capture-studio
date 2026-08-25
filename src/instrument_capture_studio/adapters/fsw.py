from dataclasses import dataclass
from typing import Any, Protocol

from instrument_capture_studio.adapters.driver_guard import DriverErrorGuard
from instrument_capture_studio.adapters.interfaces import (
    SpectrumAnalyzerAdapter,
)
from instrument_capture_studio.core.models import (
    InstrumentState,
    InstrumentStatus,
)
from instrument_capture_studio.core.results import (
    SpectrumResult,
)


class FSWDriverProtocol(Protocol):
    """FSW 商业 Adapter 所依赖的底层 Driver 能力。"""

    @property
    def is_connected(self) -> bool:
        ...

    @property
    def state(self) -> Any:
        ...

    @property
    def identity(self) -> Any:
        ...

    def connect(self) -> Any:
        ...

    def disconnect(self) -> None:
        ...

    def set_center_frequency(
        self,
        value_hz: float,
    ) -> None:
        ...

    def set_span(
        self,
        value_hz: float,
    ) -> None:
        ...

    def set_rbw(
        self,
        value_hz: float,
    ) -> None:
        ...

    def set_vbw(
        self,
        value_hz: float,
    ) -> None:
        ...

    def set_trigger_source(
        self,
        source: str,
    ) -> None:
        ...

    def acquire_trace_ascii(
        self,
        *,
        channel: int = 1,
        window: int = 1,
        trace: int = 1,
    ) -> Any:
        ...


@dataclass(frozen=True)
class FSWConfig:
    """第一版 FSW 商业采集配置。"""

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
        super().__init__(
            name="FSW",
            address=address,
        )

        self._driver = DriverErrorGuard(driver)
        self._config = config or FSWConfig()

    def connect(self) -> None:
        self._driver.connect()

    def disconnect(self) -> None:
        self._driver.disconnect()

    def is_connected(self) -> bool:
        return bool(
            self._driver.is_connected
        )

    def get_status(self) -> InstrumentStatus:
        identity = self._driver.identity

        return InstrumentStatus(
            name=self.name,
            address=self.address,
            state=self._map_state(),
            model=(
                getattr(identity, "model", None)
                if identity is not None
                else None
            ),
            serial_number=(
                getattr(
                    identity,
                    "serial_number",
                    None,
                )
                if identity is not None
                else None
            ),
            firmware_version=(
                getattr(
                    identity,
                    "firmware",
                    None,
                )
                if identity is not None
                else None
            ),
        )

    def acquire_spectrum(
        self,
    ) -> SpectrumResult:
        self._apply_configuration()

        config = self._config

        trace = (
            self._driver.acquire_trace_ascii(
                channel=config.channel,
                window=config.window,
                trace=config.trace,
            )
        )

        return SpectrumResult(
            frequencies_hz=list(
                trace.frequencies_hz
            ),
            amplitudes_dbm=list(
                trace.levels
            ),
            metadata={
                "start_hz": trace.start_hz,
                "stop_hz": trace.stop_hz,
                "channel": config.channel,
                "window": config.window,
                "trace": config.trace,
                "transfer_format": "ASCII",
            },
        )

    def _apply_configuration(
        self,
    ) -> None:
        config = self._config

        if (
            config.center_frequency_hz
            is not None
        ):
            self._driver.set_center_frequency(
                config.center_frequency_hz
            )

        if config.span_hz is not None:
            self._driver.set_span(
                config.span_hz
            )

        if config.rbw_hz is not None:
            self._driver.set_rbw(
                config.rbw_hz
            )

        if config.vbw_hz is not None:
            self._driver.set_vbw(
                config.vbw_hz
            )

        if (
            config.trigger_source
            is not None
        ):
            self._driver.set_trigger_source(
                config.trigger_source
            )

    def _map_state(
        self,
    ) -> InstrumentState:
        raw_state = self._driver.state

        value = getattr(
            raw_state,
            "value",
            str(raw_state),
        )

        mapping = {
            "disconnected": (
                InstrumentState.DISCONNECTED
            ),
            "connecting": (
                InstrumentState.CONNECTING
            ),
            "connected": (
                InstrumentState.CONNECTED
            ),
            "ready": (
                InstrumentState.CONNECTED
            ),
            "busy": (
                InstrumentState.BUSY
            ),
            "recovering": (
                InstrumentState.CONNECTING
            ),
            "error": (
                InstrumentState.ERROR
            ),
        }

        return mapping.get(
            str(value).lower(),
            InstrumentState.ERROR,
        )
