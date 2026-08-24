class InstrumentCaptureStudioError(Exception):
    """Instrument Capture Studio 所有业务异常的基类。"""


class InstrumentError(InstrumentCaptureStudioError):
    """仪表相关异常的基类。"""


class InstrumentConnectionError(InstrumentError):
    """仪表连接失败。"""


class InstrumentTimeoutError(InstrumentError):
    """仪表操作超时。"""


class InstrumentCommunicationError(InstrumentError):
    """仪表通信失败。"""


class InstrumentBusyError(InstrumentError):
    """仪表当前忙，无法执行操作。"""


class CaptureError(InstrumentCaptureStudioError):
    """采集任务相关异常的基类。"""


class CaptureStepError(CaptureError):
    """联合采集中的某个步骤执行失败。"""

    def __init__(self, step_name: str, message: str):
        self.step_name = step_name
        self.message = message
        super().__init__(f"{step_name}: {message}")


class CaptureCanceledError(CaptureError):
    """采集任务被用户或系统取消。"""
