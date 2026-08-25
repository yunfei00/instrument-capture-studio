from dataclasses import dataclass
from typing import Any, Protocol

from instrument_capture_studio.adapters.driver_guard import DriverErrorGuard
from instrument_capture_studio.adapters.interfaces import OscilloscopeAdapter
from instrument_capture_studio.core.models import (
    InstrumentState,
    InstrumentStatus,
)
from instrument_capture_studio.core.results import (
    MeasurementResult,
    WaveformResult,
)


class DSOX3034ADriverProtocol(Protocol):
    """DSO-X 3034A Adapter 所依赖的底层 Driver 能力。"""

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

    def define_delay(
        self,
        edge1: str,
        edge2: str,
        source: str | None = None,
    ) -> None:
        ...

    def measure_delay(
        self,
        source1: str | None = None,
        source2: str | None = None,
    ) -> float:
        ...

    def measure_n_pulses(
        self,
        source: str | None = None,
    ) -> float:
        ...

    def acquire_word_waveform(
        self,
        channel: int,
    ) -> Any:
        ...


@dataclass(frozen=True)
class DSOX3034AConfig:
    """DSO-X 3034A 在商业采集产品中的业务配置。"""

    delay_source1: str = "CHANnel1"
    delay_source2: str = "CHANnel2"
    delay_edge1: str = "+1"
    delay_edge2: str = "+1"

    cycle_count_source: str = "CHANnel1"

    waveform_channel: int = 1


class DSOX3034AAdapter(OscilloscopeAdapter):
    """Keysight DSO-X 3034A 商业产品适配器。"""

    def __init__(
        self,
        address: str,
        driver: DSOX3034ADriverProtocol,
        config: DSOX3034AConfig | None = None,
    ):
        super().__init__(
            name="DSO-X",
            address=address,
        )

        self._driver = DriverErrorGuard(driver)
        self._config = config or DSOX3034AConfig()

    def connect(self) -> None:
        self._driver.connect()

    def disconnect(self) -> None:
        self._driver.disconnect()

    def is_connected(self) -> bool:
        return bool(self._driver.is_connected)

    def get_status(self) -> InstrumentStatus:
        state = self._map_state()

        identity = self._driver.identity

        return InstrumentStatus(
            name=self.name,
            address=self.address,
            state=state,
            model=(
                getattr(identity, "model", None)
                if identity is not None
                else None
            ),
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

    def acquire_delay(self) -> MeasurementResult:
        config = self._config

        self._driver.define_delay(
            config.delay_edge1,
            config.delay_edge2,
        )

        value = self._driver.measure_delay(
            config.delay_source1,
            config.delay_source2,
        )

        return MeasurementResult(
            measurement="DELAY",
            value=value,
            unit="s",
            metadata={
                "source1": config.delay_source1,
                "source2": config.delay_source2,
                "edge1": config.delay_edge1,
                "edge2": config.delay_edge2,
            },
        )

    def acquire_cycle_count(self) -> MeasurementResult:
        config = self._config

        value = self._driver.measure_n_pulses(
            config.cycle_count_source
        )

        return MeasurementResult(
            measurement="CYCLE_COUNT",
            value=value,
            unit="count",
            metadata={
                "source": config.cycle_count_source,
                "backend_measurement": "NPUlSes",
            },
        )

    def acquire_waveform(self) -> WaveformResult:
        config = self._config

        waveform = self._driver.acquire_word_waveform(
            config.waveform_channel
        )

        preamble = waveform.preamble

        sample_rate_hz = None

        if preamble.x_increment > 0:
            sample_rate_hz = 1.0 / preamble.x_increment

        return WaveformResult(
            channel=f"CH{config.waveform_channel}",
            time_s=list(waveform.time_seconds),
            voltage_v=list(waveform.voltage_volts),
            sample_rate_hz=sample_rate_hz,
            metadata={
                "raw_points": len(waveform.raw_samples),
                "acquisition_type": preamble.acquisition_type,
            },
        )

    def _map_state(self) -> InstrumentState:
        raw_state = self._driver.state

        value = getattr(
            raw_state,
            "value",
            str(raw_state),
        )

        mapping = {
            "disconnected": InstrumentState.DISCONNECTED,
            "connecting": InstrumentState.CONNECTING,
            "connected": InstrumentState.CONNECTED,
            "ready": InstrumentState.CONNECTED,
            "busy": InstrumentState.BUSY,
            "recovering": InstrumentState.CONNECTING,
            "error": InstrumentState.ERROR,
        }

        return mapping.get(
            str(value).lower(),
            InstrumentState.ERROR,
        )
