from types import SimpleNamespace

from instrument_capture_studio.adapters.dsox3034a import (
    DSOX3034AAdapter,
    DSOX3034AConfig,
)
from instrument_capture_studio.core.models import InstrumentState


class FakeState:
    def __init__(self, value: str):
        self.value = value


class FakeDSOX3034ADriver:
    def __init__(self):
        self._connected = False
        self._state = FakeState("disconnected")
        self._identity = None

        self.last_delay_definition = None
        self.last_delay_sources = None
        self.last_pulse_source = None
        self.last_waveform_channel = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def state(self):
        return self._state

    @property
    def identity(self):
        return self._identity

    def connect(self):
        self._connected = True
        self._state = FakeState("ready")

        self._identity = SimpleNamespace(
            model="DSO-X 3034A",
            serial_number="MY12345678",
            firmware="02.50.2020010100",
        )

        return self._identity

    def disconnect(self) -> None:
        self._connected = False
        self._state = FakeState("disconnected")

    def define_delay(
        self,
        edge1: str,
        edge2: str,
        source: str | None = None,
    ) -> None:
        self.last_delay_definition = (
            edge1,
            edge2,
            source,
        )

    def measure_delay(
        self,
        source1: str | None = None,
        source2: str | None = None,
    ) -> float:
        self.last_delay_sources = (
            source1,
            source2,
        )

        return 1.25e-6

    def measure_n_pulses(
        self,
        source: str | None = None,
    ) -> float:
        self.last_pulse_source = source
        return 12.0

    def acquire_word_waveform(
        self,
        channel: int,
    ):
        self.last_waveform_channel = channel

        return SimpleNamespace(
            raw_samples=(
                100,
                200,
                300,
            ),
            time_seconds=(
                0.0,
                1e-6,
                2e-6,
            ),
            voltage_volts=(
                0.1,
                0.2,
                0.3,
            ),
            preamble=SimpleNamespace(
                x_increment=1e-6,
                acquisition_type=2,
            ),
        )


def make_adapter(
    config: DSOX3034AConfig | None = None,
):
    driver = FakeDSOX3034ADriver()

    adapter = DSOX3034AAdapter(
        address="TCPIP0::192.168.1.10::inst0::INSTR",
        driver=driver,
        config=config,
    )

    return adapter, driver


def test_connect_status_and_disconnect():
    adapter, driver = make_adapter()

    assert adapter.is_connected() is False

    adapter.connect()

    assert adapter.is_connected() is True

    status = adapter.get_status()

    assert status.state == InstrumentState.CONNECTED
    assert status.model == "DSO-X 3034A"
    assert status.serial_number == "MY12345678"
    assert status.firmware_version == "02.50.2020010100"

    adapter.disconnect()

    assert adapter.is_connected() is False

    status = adapter.get_status()

    assert status.state == InstrumentState.DISCONNECTED


def test_acquire_delay_maps_business_configuration():
    config = DSOX3034AConfig(
        delay_source1="CHANnel1",
        delay_source2="CHANnel2",
        delay_edge1="+1",
        delay_edge2="-1",
    )

    adapter, driver = make_adapter(config)

    result = adapter.acquire_delay()

    assert driver.last_delay_definition == (
        "+1",
        "-1",
        None,
    )

    assert driver.last_delay_sources == (
        "CHANnel1",
        "CHANnel2",
    )

    assert result.measurement == "DELAY"
    assert result.value == 1.25e-6
    assert result.unit == "s"

    assert result.metadata == {
        "source1": "CHANnel1",
        "source2": "CHANnel2",
        "edge1": "+1",
        "edge2": "-1",
    }


def test_acquire_cycle_count_maps_to_negative_pulses():
    config = DSOX3034AConfig(
        cycle_count_source="CHANnel3",
    )

    adapter, driver = make_adapter(config)

    result = adapter.acquire_cycle_count()

    assert driver.last_pulse_source == "CHANnel3"

    assert result.measurement == "CYCLE_COUNT"
    assert result.value == 12.0
    assert result.unit == "count"

    assert result.metadata["source"] == "CHANnel3"
    assert (
        result.metadata["backend_measurement"]
        == "NPUlSes"
    )


def test_acquire_waveform_converts_driver_result():
    config = DSOX3034AConfig(
        waveform_channel=2,
    )

    adapter, driver = make_adapter(config)

    result = adapter.acquire_waveform()

    assert driver.last_waveform_channel == 2

    assert result.channel == "CH2"

    assert result.time_s == [
        0.0,
        1e-6,
        2e-6,
    ]

    assert result.voltage_v == [
        0.1,
        0.2,
        0.3,
    ]

    assert result.points == 3
    assert result.sample_rate_hz == 1e6

    assert result.metadata["raw_points"] == 3
    assert result.metadata["acquisition_type"] == 2


def test_get_configuration_returns_snapshot():
    config = DSOX3034AConfig(
        delay_source1="CHANnel1",
        delay_source2="CHANnel2",
        delay_edge1="+1",
        delay_edge2="-1",
        cycle_count_source="CHANnel3",
        waveform_channel=2,
    )

    adapter, _ = make_adapter(
        config
    )

    snapshot = (
        adapter.get_configuration()
    )

    assert snapshot == {
        "delay_source1": "CHANnel1",
        "delay_source2": "CHANnel2",
        "delay_edge1": "+1",
        "delay_edge2": "-1",
        "cycle_count_source": "CHANnel3",
        "waveform_channel": 2,
    }

    snapshot[
        "waveform_channel"
    ] = 4

    assert (
        adapter.get_configuration()[
            "waveform_channel"
        ]
        == 2
    )
