from types import SimpleNamespace

import pytest

from instrument_capture_studio.app.recipe_debug import RecipeDebugSession, RecipeDebugState


class FakeIdentity:
    def __init__(self, model: str):
        self.model = model


class FakeWaveform:
    def __init__(self, points: int = 4):
        self.raw_samples = tuple(range(points))
        self.preamble = SimpleNamespace(x_increment=1e-9)


class FakeSpectrum:
    def __init__(self, points: int = 5):
        self.levels = tuple(float(index) for index in range(points))
        self.start_hz = 700e6
        self.stop_hz = 800e6


class FakeFSW:
    def __init__(self):
        self.calls = []
        self.trigger = "IMM"

    def connect(self):
        self.calls.append(("connect",))
        return FakeIdentity("FSW")

    def disconnect(self):
        self.calls.append(("disconnect",))

    def get_sweep_time(self):
        self.calls.append(("get_sweep_time",))
        return 0.96

    def set_trigger_source(self, source):
        self.trigger = source
        self.calls.append(("set_trigger_source", source))

    def arm_trace_ascii(self, *, channel=1):
        self.calls.append(("arm_trace_ascii", channel))

    def wait_and_read_trace_ascii(self, **kwargs):
        self.calls.append(("wait_and_read_trace_ascii", kwargs.get("timeout_s")))
        return FakeSpectrum()

    def acquire_trace_ascii(self, **kwargs):
        self.calls.append(("acquire_trace_ascii", kwargs.get("timeout_s")))
        return FakeSpectrum(6)

    def abort(self):
        self.calls.append(("abort",))


class FakeDSOX:
    def __init__(self):
        self.calls = []
        self.position = 0.0
        self.scale = 1e-6
        self.mode = "MAIN"
        self.reference = "CENT"

    def connect(self):
        self.calls.append(("connect",))
        return FakeIdentity("DSO-X 3034A")

    def disconnect(self):
        self.calls.append(("disconnect",))

    def write(self, command):
        self.calls.append(("write", command))
        if command == ":TIMebase:MODE MAIN":
            self.mode = "MAIN"
        if command == ":TIMebase:REFerence CENTer":
            self.reference = "CENT"

    def query(self, command):
        self.calls.append(("query", command))
        if command == ":TIMebase:MODE?":
            return self.mode
        if command == ":TIMebase:REFerence?":
            return self.reference
        raise AssertionError(command)

    def set_timebase_position(self, value):
        self.position = float(value)
        self.calls.append(("set_timebase_position", self.position))

    def get_timebase_position(self):
        self.calls.append(("get_timebase_position",))
        return self.position

    def set_timebase_scale(self, value):
        self.scale = float(value)
        self.calls.append(("set_timebase_scale", self.scale))

    def get_timebase_scale(self):
        self.calls.append(("get_timebase_scale",))
        return self.scale

    def acquire_word_waveform(self, channel):
        self.calls.append(("acquire_word_waveform", channel))
        return FakeWaveform()

    def abort(self):
        self.calls.append(("abort",))


def test_new_recipe_debug_sequence_uses_fsw_sweep_time_and_two_scope_windows():
    fsw = FakeFSW()
    dsox = FakeDSOX()
    session = RecipeDebugSession(fsw, dsox, fsw_timeout_s=3.0)

    assert session.connect()["state"] == RecipeDebugState.CONNECTED.value

    sweep = session.read_sweep_time()
    assert sweep["sweep_time_s"] == pytest.approx(0.96)
    assert sweep["sync_position_s"] == pytest.approx(0.48)
    assert sweep["sync_scale_s_per_div"] == pytest.approx(0.096)

    sync_config = session.configure_sync_scope()
    assert sync_config["requested_position_s"] == pytest.approx(0.48)
    assert sync_config["requested_scale_s_per_div"] == pytest.approx(0.096)
    assert sync_config["position_readback_s"] == pytest.approx(0.48)
    assert sync_config["scale_readback_s_per_div"] == pytest.approx(0.096)
    assert ("write", ":TIMebase:MODE MAIN") in dsox.calls
    assert ("write", ":TIMebase:REFerence CENTer") in dsox.calls

    session.arm_fsw_ext()
    assert fsw.trigger == "EXT"
    assert ("set_trigger_source", "EXT") in fsw.calls
    assert ("arm_trace_ascii", 1) in fsw.calls

    first_scope = session.capture_sync_scope(1)
    assert first_scope["points"] == 4

    ext = session.read_ext_spectrum()
    assert ext["points"] == 5

    followup = session.configure_followup_scope(
        position_s=0.484,
        scale_s_per_div=20e-9,
    )
    assert followup["position_readback_s"] == pytest.approx(0.484)
    assert followup["scale_readback_s_per_div"] == pytest.approx(20e-9)

    second_scope = session.capture_followup_scope(1)
    assert second_scope["points"] == 4

    freerun = session.capture_freerun_spectrum()
    assert freerun["points"] == 6
    assert fsw.trigger == "IMM"
    assert session.state is RecipeDebugState.COMPLETE

    reset = session.reset()
    assert reset["errors"] == []
    assert session.state is RecipeDebugState.CLOSED
    assert ("abort",) in fsw.calls
    assert ("abort",) in dsox.calls


def test_debug_session_rejects_out_of_order_steps():
    session = RecipeDebugSession(FakeFSW(), FakeDSOX(), fsw_timeout_s=3.0)
    session.connect()
    with pytest.raises(RuntimeError, match="sweep_time_read"):
        session.configure_sync_scope()
