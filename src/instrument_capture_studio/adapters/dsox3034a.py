from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Iterator, Protocol

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
    def is_connected(self) -> bool: ...

    @property
    def state(self) -> Any: ...

    @property
    def identity(self) -> Any: ...

    def connect(self) -> Any: ...
    def disconnect(self) -> None: ...

    def set_timebase_scale(self, scale: float) -> None: ...
    def get_trigger_sweep(self) -> str: ...
    def set_trigger_sweep(self, sweep: str) -> None: ...
    def get_acquisition_type(self) -> str: ...
    def set_acquisition_type(self, acquisition_type: str) -> None: ...

    def define_delay(
        self,
        edge1: str,
        edge2: str,
        source: str | None = None,
    ) -> None: ...

    def measure_delay(
        self,
        source1: str | None = None,
        source2: str | None = None,
    ) -> float: ...

    def measure_n_pulses(
        self,
        source: str | None = None,
    ) -> float: ...

    def acquire_word_waveform(
        self,
        channel: int,
    ) -> Any: ...


@dataclass(frozen=True)
class DSOX3034AConfig:
    """DSO-X 3034A 在商业采集产品中的业务配置。"""

    delay_source1: str = "CHANnel1"
    delay_source2: str = "CHANnel2"
    delay_edge1: str = "+1"
    delay_edge2: str = "+1"
    cycle_count_source: str = "CHANnel1"
    waveform_channel: int = 1
    delay_timebase_scale_s: float = 5.0e-7
    cycle_timebase_scale_s: float = 1.0e-4

    def __post_init__(self) -> None:
        if self.waveform_channel not in {1, 2, 3, 4}:
            raise ValueError("waveform_channel must be between 1 and 4")
        if self.delay_timebase_scale_s <= 0:
            raise ValueError("delay_timebase_scale_s must be greater than 0")
        if self.cycle_timebase_scale_s <= 0:
            raise ValueError("cycle_timebase_scale_s must be greater than 0")


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

    def get_configuration(self) -> dict[str, object]:
        return dict(asdict(self._config))

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

    @contextmanager
    def standalone_auto_trigger(self) -> Iterator[dict[str, str]]:
        """Use deterministic one-shot settings for DSO-X-only capture.

        Two front-panel settings can make ``:DIGitize`` exceed the normal VISA
        timeout even when the instrument and LAN link are healthy:

        * NORM trigger sweep can wait indefinitely for a trigger.
        * AVERage acquisition waits until the configured average count is full.

        A standalone training sample is not meant to inherit either condition,
        so this scope temporarily uses AUTO + NORMal for its two physical
        acquisitions. The original front-panel settings are restored when the
        recipe exits. The paired EXT recipe never enters this context and keeps
        its real trigger behavior unchanged.
        """

        original_sweep = str(self._driver.get_trigger_sweep()).strip().upper()
        original_acquisition = str(
            self._driver.get_acquisition_type()
        ).strip().upper()

        sweep_changed = original_sweep != "AUTO"
        acquisition_changed = original_acquisition not in {"NORM", "NORMAL"}

        if sweep_changed:
            self._driver.set_trigger_sweep("AUTO")
        if acquisition_changed:
            self._driver.set_acquisition_type("NORMal")

        state = {
            "trigger_sweep_original": original_sweep,
            "trigger_sweep_used": "AUTO",
            "acquisition_type_original": original_acquisition,
            "acquisition_type_used": "NORM",
        }
        try:
            yield state
        finally:
            if acquisition_changed and original_acquisition in {
                "NORM",
                "NORMAL",
                "AVER",
                "AVERAGE",
                "HRES",
                "HRESOLUTION",
                "PEAK",
            }:
                try:
                    self._driver.set_acquisition_type(original_acquisition)
                except Exception:
                    pass
            if sweep_changed and original_sweep in {"AUTO", "NORM"}:
                try:
                    self._driver.set_trigger_sweep(original_sweep)
                except Exception:
                    # Disconnect follows the workflow. Do not hide the primary
                    # acquisition result if restoring front-panel state fails.
                    pass

    def acquire_delay(self) -> MeasurementResult:
        """Legacy measurement-only DELAY query."""
        config = self._config
        self._driver.define_delay(
            config.delay_edge1,
            config.delay_edge2,
        )
        value = self._driver.measure_delay(
            config.delay_source1,
            config.delay_source2,
        )
        return self._delay_result(value)

    def acquire_cycle_count(self) -> MeasurementResult:
        """Legacy measurement-only cycle-count query."""
        config = self._config
        value = self._driver.measure_n_pulses(config.cycle_count_source)
        return self._cycle_result(value)

    def acquire_waveform(self) -> WaveformResult:
        """Acquire one generic waveform using the selected channel."""
        return self._convert_waveform(
            self._driver.acquire_word_waveform(self._config.waveform_channel),
            sample_kind="generic",
            timebase_scale_s=None,
        )

    def acquire_delay_group(self) -> tuple[MeasurementResult, WaveformResult]:
        """Acquire the DELAY training group from one oscilloscope acquisition.

        The qualified default timebase is 500 ns/div. ``acquire_word_waveform``
        performs the DSO-X DIGitize operation; in the EXT recipe this is the
        first oscilloscope acquisition after the FSW has been armed and is
        therefore the hardware event expected to trigger the FSW.
        """
        config = self._config
        self._driver.set_timebase_scale(config.delay_timebase_scale_s)
        self._driver.define_delay(
            config.delay_edge1,
            config.delay_edge2,
        )
        raw_waveform = self._driver.acquire_word_waveform(config.waveform_channel)
        value = self._driver.measure_delay(
            config.delay_source1,
            config.delay_source2,
        )
        return (
            self._delay_result(value),
            self._convert_waveform(
                raw_waveform,
                sample_kind="delay",
                timebase_scale_s=config.delay_timebase_scale_s,
            ),
        )

    def acquire_cycle_group(self) -> tuple[MeasurementResult, WaveformResult]:
        """Acquire the CYCLE_COUNT training group as a second DSO-X capture.

        The qualified default timebase is 100 us/div. This is deliberately a
        new DIGitize/acquisition and is not the same waveform as the DELAY
        group.
        """
        config = self._config
        self._driver.set_timebase_scale(config.cycle_timebase_scale_s)
        raw_waveform = self._driver.acquire_word_waveform(config.waveform_channel)
        value = self._driver.measure_n_pulses(config.cycle_count_source)
        return (
            self._cycle_result(value),
            self._convert_waveform(
                raw_waveform,
                sample_kind="cycle_count",
                timebase_scale_s=config.cycle_timebase_scale_s,
            ),
        )

    def _delay_result(self, value: float) -> MeasurementResult:
        config = self._config
        return MeasurementResult(
            measurement="DELAY",
            value=value,
            unit="s",
            metadata={
                "source1": config.delay_source1,
                "source2": config.delay_source2,
                "edge1": config.delay_edge1,
                "edge2": config.delay_edge2,
                "timebase_scale_s": config.delay_timebase_scale_s,
            },
        )

    def _cycle_result(self, value: float) -> MeasurementResult:
        config = self._config
        return MeasurementResult(
            measurement="CYCLE_COUNT",
            value=value,
            unit="count",
            metadata={
                "source": config.cycle_count_source,
                "backend_measurement": "NPUlSes",
                "timebase_scale_s": config.cycle_timebase_scale_s,
            },
        )

    def _convert_waveform(
        self,
        waveform: Any,
        *,
        sample_kind: str,
        timebase_scale_s: float | None,
    ) -> WaveformResult:
        config = self._config
        preamble = waveform.preamble
        sample_rate_hz = None
        if preamble.x_increment > 0:
            sample_rate_hz = 1.0 / preamble.x_increment
        metadata: dict[str, object] = {
            "raw_points": len(waveform.raw_samples),
            "acquisition_type": preamble.acquisition_type,
            "sample_kind": sample_kind,
        }
        if timebase_scale_s is not None:
            metadata["timebase_scale_s"] = timebase_scale_s
        return WaveformResult(
            channel=f"CH{config.waveform_channel}",
            time_s=list(waveform.time_seconds),
            voltage_v=list(waveform.voltage_volts),
            sample_rate_hz=sample_rate_hz,
            metadata=metadata,
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
