from typing import Any

from instrument_capture_studio.core.exceptions import (
    InstrumentBusyError,
    InstrumentCaptureStudioError,
    InstrumentCommunicationError,
    InstrumentConnectionError,
    InstrumentTimeoutError,
)


class DriverErrorGuard:
    """
    Driver 与商业 Adapter 之间的异常边界。

    不直接依赖 instrument-automation-platform 包。
    只转换已知的平台运行时仪表异常；
    未知异常保持原样抛出，避免隐藏程序 Bug。
    """

    def __init__(
        self,
        driver: Any,
    ):
        self._driver = driver

    def __getattr__(
        self,
        name: str,
    ) -> Any:
        try:
            attribute = getattr(
                self._driver,
                name,
            )
        except Exception as exc:
            self._raise_translated(
                name,
                exc,
            )

        if not callable(attribute):
            return attribute

        def guarded(
            *args,
            **kwargs,
        ):
            try:
                return attribute(
                    *args,
                    **kwargs,
                )
            except Exception as exc:
                self._raise_translated(
                    name,
                    exc,
                )

        return guarded

    @staticmethod
    def _raise_translated(
        operation: str,
        exc: Exception,
    ) -> None:
        # 产品层异常不要重复包装。
        if isinstance(
            exc,
            InstrumentCaptureStudioError,
        ):
            raise exc

        names = {
            cls.__name__
            for cls in type(exc).__mro__
        }

        message = (
            f"{operation}: {exc}"
        )

        if (
            "InstrumentConnectionError"
            in names
        ):
            raise InstrumentConnectionError(
                message
            ) from exc

        if (
            "InstrumentTimeoutError"
            in names
            or "TriggerTimeoutError"
            in names
        ):
            raise InstrumentTimeoutError(
                message
            ) from exc

        if "InstrumentBusyError" in names:
            raise InstrumentBusyError(
                message
            ) from exc

        # instrument-automation-platform
        # 的其他 InstrumentError 子类统一视为
        # 产品层通信/仪表操作失败。
        if "InstrumentError" in names:
            raise InstrumentCommunicationError(
                message
            ) from exc

        # TypeError、RuntimeError 等未知异常
        # 不做转换，让它们直接暴露。
        raise exc
