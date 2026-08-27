from types import SimpleNamespace

from instrument_capture_studio.adapters.fsw import FSWAdapter, FSWConfig


class LegacyFSWDriver:
    """Model the platform driver before arm_trace_ascii was added."""

    def __init__(self):
        self.calls = []
        self.is_connected = True
        self.state = SimpleNamespace(value="ready")
        self.identity = SimpleNamespace(
            model="FSW",
            serial_number="debug",
            firmware="debug",
        )

    def connect(self):
        return self.identity

    def disconnect(self):
        return None

    def set_center_frequency(self, value):
        self.calls.append(("center", value))

    def set_span(self, value):
        self.calls.append(("span", value))

    def set_rbw(self, value):
        self.calls.append(("rbw", value))

    def set_vbw(self, value):
        self.calls.append(("vbw", value))

    def set_trigger_source(self, source):
        self.calls.append(("trigger", source))

    def set_continuous(self, enabled, channel=1):
        self.calls.append(("continuous", enabled, channel))

    def set_trace_ascii(self):
        self.calls.append(("ascii",))

    def initiate(self, channel=1):
        self.calls.append(("initiate", channel))

    def wait_operation_complete_bounded(
        self,
        timeout_s,
        *,
        poll_interval_s=0.05,
        cancel_check=None,
    ):
        self.calls.append(("wait_bounded", timeout_s, cancel_check))

    def wait_operation_complete(self):
        self.calls.append(("wait",))
        return True

    def get_start_frequency(self):
        return 699e6

    def get_stop_frequency(self):
        return 701e6

    def read_trace_ascii(self, *, window=1, trace=1):
        self.calls.append(("read", window, trace))
        return (-70.0, -50.0, -65.0)

    def acquire_trace_ascii(self, **kwargs):
        raise AssertionError("EXT compatibility path must not restart acquisition")


def test_ext_arm_and_read_work_without_new_driver_convenience_methods():
    driver = LegacyFSWDriver()
    adapter = FSWAdapter(
        address="TCPIP::debug",
        driver=driver,
        config=FSWConfig(
            center_frequency_hz=700e6,
            span_hz=2e6,
            trigger_source="IMM",
            window=2,
            trace=3,
        ),
    )

    adapter.arm_spectrum("EXT")
    result = adapter.read_armed_spectrum(
        timeout_s=5.0,
        trigger_source="EXT",
    )

    assert driver.calls == [
        ("center", 700e6),
        ("span", 2e6),
        ("trigger", "EXT"),
        ("continuous", False, 1),
        ("ascii",),
        ("initiate", 1),
        ("wait_bounded", 5.0, None),
        ("read", 2, 3),
    ]
    assert result.frequencies_hz == [699e6, 700e6, 701e6]
    assert result.amplitudes_dbm == [-70.0, -50.0, -65.0]
    assert result.metadata["trigger_source"] == "EXT"
