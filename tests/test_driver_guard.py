import pytest

from instrument_capture_studio.adapters.driver_guard import (
    DriverErrorGuard,
)
from instrument_capture_studio.core.exceptions import (
    InstrumentBusyError as ProductBusyError,
    InstrumentCommunicationError,
    InstrumentConnectionError as ProductConnectionError,
    InstrumentTimeoutError as ProductTimeoutError,
)


class FakeDriver:
    def __init__(
        self,
        exc: Exception,
    ):
        self.exc = exc

    def operation(self):
        raise self.exc


def make_exception(
    name: str,
):
    exception_type = type(
        name,
        (Exception,),
        {},
    )

    return exception_type(
        "lower-level failure"
    )


def test_connection_error_is_translated():
    driver = DriverErrorGuard(
        FakeDriver(
            make_exception(
                "InstrumentConnectionError"
            )
        )
    )

    with pytest.raises(
        ProductConnectionError,
        match="operation:",
    ):
        driver.operation()


def test_timeout_error_is_translated():
    driver = DriverErrorGuard(
        FakeDriver(
            make_exception(
                "InstrumentTimeoutError"
            )
        )
    )

    with pytest.raises(
        ProductTimeoutError,
        match="operation:",
    ):
        driver.operation()


def test_busy_error_is_translated():
    driver = DriverErrorGuard(
        FakeDriver(
            make_exception(
                "InstrumentBusyError"
            )
        )
    )

    with pytest.raises(
        ProductBusyError,
        match="operation:",
    ):
        driver.operation()


def test_platform_instrument_error_becomes_communication_error():
    PlatformInstrumentError = type(
        "InstrumentError",
        (Exception,),
        {},
    )

    PlatformTransportError = type(
        "TransportError",
        (PlatformInstrumentError,),
        {},
    )

    driver = DriverErrorGuard(
        FakeDriver(
            PlatformTransportError(
                "network lost"
            )
        )
    )

    with pytest.raises(
        InstrumentCommunicationError,
        match="network lost",
    ):
        driver.operation()


def test_programming_error_is_not_translated():
    driver = DriverErrorGuard(
        FakeDriver(
            TypeError(
                "programming bug"
            )
        )
    )

    with pytest.raises(
        TypeError,
        match="programming bug",
    ):
        driver.operation()


def test_operation_canceled_error_is_translated():
    from instrument_capture_studio.core.exceptions import (
        CaptureCanceledError,
    )

    driver = DriverErrorGuard(
        FakeDriver(
            make_exception(
                "OperationCanceledError"
            )
        )
    )

    with pytest.raises(
        CaptureCanceledError,
        match="operation:",
    ):
        driver.operation()
