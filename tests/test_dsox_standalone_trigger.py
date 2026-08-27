from instrument_capture_studio.adapters.dsox3034a import DSOX3034AAdapter


class FakeState:
    value = "ready"


class FakeDriver:
    def __init__(self):
        self._sweep = "NORM"
        self._acquisition_type = "AVER"
        self.sweep_writes = []
        self.acquisition_writes = []

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

    def get_acquisition_type(self):
        return self._acquisition_type

    def set_acquisition_type(self, value):
        normalized = str(value).upper()
        if normalized.startswith("NORM"):
            self._acquisition_type = "NORM"
        elif normalized.startswith("AVER"):
            self._acquisition_type = "AVER"
        elif normalized.startswith("HRES"):
            self._acquisition_type = "HRES"
        else:
            self._acquisition_type = normalized
        self.acquisition_writes.append(value)


def test_standalone_capture_forces_auto_and_normal_then_restores():
    driver = FakeDriver()
    adapter = DSOX3034AAdapter("TEST", driver)

    with adapter.standalone_auto_trigger() as settings:
        assert settings == {
            "trigger_sweep_original": "NORM",
            "trigger_sweep_used": "AUTO",
            "acquisition_type_original": "AVER",
            "acquisition_type_used": "NORM",
        }
        assert driver._sweep == "AUTO"
        assert driver._acquisition_type == "NORM"

    assert driver._sweep == "NORM"
    assert driver._acquisition_type == "AVER"
    assert driver.sweep_writes == ["AUTO", "NORM"]
    assert driver.acquisition_writes == ["NORMal", "AVER"]


def test_standalone_capture_avoids_redundant_writes_when_already_deterministic():
    driver = FakeDriver()
    driver._sweep = "AUTO"
    driver._acquisition_type = "NORM"
    adapter = DSOX3034AAdapter("TEST", driver)

    with adapter.standalone_auto_trigger() as settings:
        assert settings["trigger_sweep_original"] == "AUTO"
        assert settings["acquisition_type_original"] == "NORM"
        assert driver._sweep == "AUTO"
        assert driver._acquisition_type == "NORM"

    assert driver.sweep_writes == []
    assert driver.acquisition_writes == []
