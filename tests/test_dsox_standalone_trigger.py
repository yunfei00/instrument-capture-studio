from instrument_capture_studio.adapters.dsox3034a import DSOX3034AAdapter


class FakeState:
    value = "ready"


class FakeDriver:
    def __init__(self):
        self._sweep = "NORM"
        self.sweep_writes = []

    @property
    def is_connected(self):
        return True

    @property
    def state(self):
        return FakeState()

    @property
    def identity(self):
        return None

    def get_trigger_sweep(self):
        return self._sweep

    def set_trigger_sweep(self, value):
        self._sweep = value
        self.sweep_writes.append(value)


def test_standalone_auto_trigger_restores_original_sweep():
    driver = FakeDriver()
    adapter = DSOX3034AAdapter("TEST", driver)

    with adapter.standalone_auto_trigger() as original:
        assert original == "NORM"
        assert driver._sweep == "AUTO"

    assert driver._sweep == "NORM"
    assert driver.sweep_writes == ["AUTO", "NORM"]


def test_standalone_auto_trigger_keeps_auto_without_redundant_restore():
    driver = FakeDriver()
    driver._sweep = "AUTO"
    adapter = DSOX3034AAdapter("TEST", driver)

    with adapter.standalone_auto_trigger() as original:
        assert original == "AUTO"
        assert driver._sweep == "AUTO"

    assert driver.sweep_writes == []
