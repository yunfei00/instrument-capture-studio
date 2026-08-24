from abc import ABC, abstractmethod

from instrument_capture_studio.core.models import InstrumentStatus


class InstrumentAdapter(ABC):
    """商业产品层访问单台仪表的统一接口。"""

    def __init__(self, name: str, address: str):
        self.name = name
        self.address = address

    @abstractmethod
    def connect(self) -> None:
        """连接仪表。"""

    @abstractmethod
    def disconnect(self) -> None:
        """断开仪表连接。"""

    @abstractmethod
    def is_connected(self) -> bool:
        """返回当前是否已经连接。"""

    @abstractmethod
    def get_status(self) -> InstrumentStatus:
        """返回产品层统一仪表状态。"""

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()
