from collections.abc import Callable

from instrument_capture_studio.adapters.interfaces import (
    OscilloscopeAdapter,
    SpectrumAnalyzerAdapter,
)
from instrument_capture_studio.core.models import (
    CaptureResult,
)
from instrument_capture_studio.workflows.combined import (
    CombinedCaptureWorkflow,
)
from instrument_capture_studio.workflows.result_sink import (
    CaptureResultSink,
)


CancelCheck = Callable[[], bool]


def run_combined_capture(
    spectrum_analyzer: SpectrumAnalyzerAdapter,
    oscilloscope: OscilloscopeAdapter,
    *,
    job_id: str,
    fsw_timeout_s: float | None = None,
    cancel_check: CancelCheck | None = None,
    result_sink: CaptureResultSink | None = None,
) -> CaptureResult:
    """
    连接两台仪表并执行一次完整联合采集。

    连接生命周期属于应用层：
    connect -> workflow -> disconnect。
    """

    connected = []
    result: CaptureResult | None = None

    try:
        spectrum_analyzer.connect()
        connected.append(
            spectrum_analyzer
        )

        oscilloscope.connect()
        connected.append(
            oscilloscope
        )

        workflow = CombinedCaptureWorkflow(
            spectrum_analyzer=(
                spectrum_analyzer
            ),
            oscilloscope=oscilloscope,
            fsw_timeout_s=fsw_timeout_s,
            cancel_check=cancel_check,
            result_sink=result_sink,
        )

        result = workflow.run(
            job_id
        )

        return result

    finally:
        disconnect_errors = []

        for adapter in reversed(
            connected
        ):
            try:
                adapter.disconnect()
            except Exception as exc:
                disconnect_errors.append(
                    (
                        adapter.name,
                        type(exc).__name__,
                        str(exc),
                    )
                )

        if (
            result is not None
            and disconnect_errors
        ):
            result.metadata[
                "disconnect_errors"
            ] = disconnect_errors
