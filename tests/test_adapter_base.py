from instrument_capture_studio.adapters.base import InstrumentAdapter
from instrument_capture_studio.core.models import (
    InstrumentState,
    InstrumentStatus,
)


class FakeAdapter(InstrumentAdapter):

    def __init__(self):
        super().__init__(
            name="Fake Instrument",
            address="TCPIP0::TEST::INSTR",
        )

        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    def get_status(self) -> InstrumentStatus:
        return InstrumentStatus(
            name=self.name,
            address=self.address,
            state=(
                InstrumentState.CONNECTED
                if self.connected
                else InstrumentState.DISCONNECTED
            ),
        )


def test_adapter_connect_disconnect():
    adapter = FakeAdapter()

    assert adapter.is_connected() is False

    adapter.connect()

    assert adapter.is_connected() is True
    assert adapter.get_status().state == InstrumentState.CONNECTED

    adapter.disconnect()

    assert adapter.is_connected() is False


def test_adapter_context_manager():
    adapter = FakeAdapter()

    with adapter:
        assert adapter.is_connected() is True

    assert adapter.is_connected() is False
