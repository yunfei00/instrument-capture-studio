from types import SimpleNamespace

import pytest

from instrument_capture_studio.adapters.fsw import FSWAdapter, FSWConfig
from instrument_capture_studio.core.models import InstrumentState


class FakeState:
    def __init__(self, value: str):
        self.value = value


class FakeFSWDriver:
    def __init__(self):
        self._connected = False
        self._state = FakeState("disconnected")
        self._identity = None
        self.calls = []

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
            model="FSW",
            serial_number="123456",
            firmware="6.30",
        )
        return self._identity

    def disconnect(self) -> None:
        self._connected = False
        self._state = FakeState("disconnected")

    def set_center_frequency(self, value_hz: float) -> None:
        self.calls.append(("center", value_hz))

    def set_span(self, value_hz: float) -> None:
        self.calls.append(("span", value_hz))

    def set_rbw(self, value_hz: float) -> None:
        self.calls.append(("rbw", value_hz))

    def set_vbw(self, value_hz: float) -> None:
        self.calls.append(("vbw", value_hz))

    def get_sweep_time(self) -> float:
        self.calls.append(("sweep_time",))
        return 0.2

    def set_trigger_source(self, source: str) -> None:
        self.calls.append(("trigger", source))

    def arm_trace_ascii(self, *, channel: int = 1) -> None:
        self.calls.append(("arm", channel))

    def wait_and_read_trace_ascii(
        self,
        *,
        window: int = 1,
        trace: int = 1,
        timeout_s: float | None = None,
        cancel_check=None,
    ):
        self.calls.append(("wait_read", window, trace, timeout_s, cancel_check))
        return self._trace()

    def acquire_trace_ascii(
        self,
        *,
        channel: int = 1,
        window: int = 1,
        trace: int = 1,
        timeout_s: float | None = None,
        cancel_check=None,
    ):
        self.calls.append(
            ("acquire", channel, window, trace, timeout_s, cancel_check)
        )
        return self._trace()

    @staticmethod
    def _trace():
        return SimpleNamespace(
            frequencies_hz=(100e6, 150e6, 200e6),
            levels=(-80.0, -60.0, -70.0),
            start_hz=100e6,
            stop_hz=200e6,
        )


class ZeroSpanFSWDriver(FakeFSWDriver):
    @staticmethod
    def _trace():
        return SimpleNamespace(
            frequencies_hz=(700e6, 700e6, 700e6),
            levels=(-80.0, -60.0, -70.0),
            start_hz=700e6,
            stop_hz=700e6,
        )


def make_adapter(config: FSWConfig | None = None):
    driver = FakeFSWDriver()
    adapter = FSWAdapter(
        address="TCPIP0::192.168.1.20::inst0::INSTR",
        driver=driver,
        config=config,
    )
    return adapter, driver


def test_connect_status_and_disconnect():
    adapter, _ = make_adapter()
    assert adapter.is_connected() is False
    adapter.connect()
    status = adapter.get_status()
    assert status.state == InstrumentState.CONNECTED
    assert status.model == "FSW"
    assert status.serial_number == "123456"
    assert status.firmware_version == "6.30"
    adapter.disconnect()
    assert adapter.is_connected() is False


def test_acquire_spectrum_applies_configuration():
    config = FSWConfig(
        center_frequency_hz=150e6,
        span_hz=100e6,
        rbw_hz=1e6,
        vbw_hz=3e6,
        trigger_source="EXT",
        channel=1,
        window=2,
        trace=3,
    )
    adapter, driver = make_adapter(config)
    result = adapter.acquire_spectrum()

    assert driver.calls == [
        ("center", 150e6),
        ("span", 100e6),
        ("rbw", 1e6),
        ("vbw", 3e6),
        ("trigger", "EXT"),
        ("acquire", 1, 2, 3, None, None),
    ]
    assert result.points == 3
    assert result.metadata["trigger_source"] == "EXT"


def test_default_configuration_does_not_change_measurement_settings():
    adapter, driver = make_adapter()
    result = adapter.acquire_spectrum()
    assert driver.calls == [("acquire", 1, 1, 1, None, None)]
    assert result.points == 3


def test_acquire_spectrum_passes_timeout_and_cancel():
    adapter, driver = make_adapter()

    def cancel_check():
        return False

    result = adapter.acquire_spectrum(timeout_s=7.5, cancel_check=cancel_check)
    assert driver.calls == [("acquire", 1, 1, 1, 7.5, cancel_check)]
    assert result.points == 3


def test_arm_ext_then_wait_read_keeps_trigger_before_arm():
    config = FSWConfig(
        center_frequency_hz=700e6,
        span_hz=0,
        rbw_hz=1e6,
        vbw_hz=3e6,
        trigger_source="IMM",
        channel=1,
        window=2,
        trace=3,
    )
    adapter, driver = make_adapter(config)

    adapter.arm_spectrum("EXT")
    result = adapter.read_armed_spectrum(timeout_s=5.0, trigger_source="EXT")

    assert driver.calls == [
        ("center", 700e6),
        ("span", 0.0),
        ("rbw", 1e6),
        ("vbw", 3e6),
        ("trigger", "EXT"),
        ("arm", 1),
        ("wait_read", 2, 3, 5.0, None),
    ]
    assert result.metadata["trigger_source"] == "EXT"


def test_zero_span_uses_sweep_time_as_trace_axis():
    driver = ZeroSpanFSWDriver()
    adapter = FSWAdapter(
        address="TCPIP0::192.168.1.20::inst0::INSTR",
        driver=driver,
        config=FSWConfig(trigger_source="IMM"),
    )

    result = adapter.acquire_spectrum()

    assert result.axis_kind == "time"
    assert result.time_s == pytest.approx([0.0, 0.1, 0.2])
    assert result.frequencies_hz == [700e6, 700e6, 700e6]
    assert result.metadata["zero_span"] is True
    assert result.metadata["center_frequency_hz"] == 700e6
    assert result.metadata["span_hz"] == 0.0
    assert result.metadata["sweep_time_s"] == pytest.approx(0.2)
    assert driver.calls == [
        ("trigger", "IMM"),
        ("acquire", 1, 1, 1, None, None),
        ("sweep_time",),
    ]


def test_imm_override_does_not_mutate_saved_configuration():
    adapter, driver = make_adapter(FSWConfig(trigger_source="EXT"))
    result = adapter.acquire_spectrum_with_trigger("IMM")

    assert driver.calls == [
        ("trigger", "IMM"),
        ("acquire", 1, 1, 1, None, None),
    ]
    assert result.metadata["trigger_source"] == "IMM"
    assert adapter.get_configuration()["trigger_source"] == "EXT"


def test_get_configuration_returns_snapshot():
    config = FSWConfig(
        center_frequency_hz=600e6,
        span_hz=200e6,
        rbw_hz=1e6,
        vbw_hz=3e6,
        trigger_source="EXT",
        channel=1,
        window=2,
        trace=3,
    )
    adapter, _ = make_adapter(config)
    snapshot = adapter.get_configuration()
    assert snapshot["center_frequency_hz"] == 600e6
    assert snapshot["span_hz"] == 200e6
    assert snapshot["trigger_source"] == "EXT"
    snapshot["span_hz"] = 123
    assert adapter.get_configuration()["span_hz"] == 200e6
