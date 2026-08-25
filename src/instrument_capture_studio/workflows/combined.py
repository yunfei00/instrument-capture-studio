from collections.abc import Callable

from instrument_capture_studio.adapters.interfaces import (
    OscilloscopeAdapter,
    SpectrumAnalyzerAdapter,
)
from instrument_capture_studio.core.models import (
    CaptureResult,
)
from instrument_capture_studio.workflows.base import (
    CaptureStepDefinition,
    CaptureWorkflow,
)
from instrument_capture_studio.workflows.context import (
    CaptureContext,
)
from instrument_capture_studio.workflows.execution import (
    StepExecutionContext,
)
from instrument_capture_studio.workflows.runner import (
    SequentialWorkflowRunner,
)
from instrument_capture_studio.workflows.result_sink import (
    CaptureResultSink,
    InMemoryResultSink,
)


CancelCheck = Callable[[], bool]


class CombinedCaptureWorkflow(CaptureWorkflow):
    """FSW + DSO-X 一次完整联合采集流程。"""

    def __init__(
        self,
        spectrum_analyzer: SpectrumAnalyzerAdapter,
        oscilloscope: OscilloscopeAdapter,
        *,
        fsw_timeout_s: float | None = None,
        cancel_check: CancelCheck | None = None,
        result_sink: CaptureResultSink | None = None,
    ):
        self._spectrum_analyzer = (
            spectrum_analyzer
        )
        self._oscilloscope = (
            oscilloscope
        )
        self._cancel_check = (
            cancel_check
        )

        self._result_sink = (
            result_sink
            or InMemoryResultSink()
        )

        self._current_job_id: str | None = None
        self._output_files: list[str] = []

        self._steps = (
            CaptureStepDefinition(
                "fsw_spectrum",
                timeout_s=fsw_timeout_s,
            ),
            CaptureStepDefinition(
                "dsox_delay",
            ),
            CaptureStepDefinition(
                "dsox_cycle_count",
            ),
            CaptureStepDefinition(
                "dsox_waveform",
            ),
            CaptureStepDefinition(
                "save_result",
            ),
        )

        self._context = CaptureContext()

    @property
    def steps(
        self,
    ) -> tuple[CaptureStepDefinition, ...]:
        return self._steps

    @property
    def context(
        self,
    ) -> CaptureContext:
        return self._context

    def run(
        self,
        job_id: str,
    ) -> CaptureResult:
        # Workflow 对象允许重复使用；
        # 每个新 Job 必须从全新的上下文开始。
        self._context = CaptureContext()
        self._current_job_id = job_id
        self._output_files = []

        runner = SequentialWorkflowRunner(
            steps=self.steps,
            executors={
                "fsw_spectrum": (
                    self._acquire_spectrum
                ),
                "dsox_delay": (
                    self._acquire_delay
                ),
                "dsox_cycle_count": (
                    self._acquire_cycle_count
                ),
                "dsox_waveform": (
                    self._acquire_waveform
                ),
                "save_result": (
                    self._save_result
                ),
            },
            cancel_check=self._cancel_check,
        )

        result = runner.run(
            job_id
        )

        result.metadata[
            "capture_complete"
        ] = self._context.is_complete

        result.metadata[
            "result_saved"
        ] = bool(
            self._context.metadata.get(
                "result_saved",
                False,
            )
        )

        result.output_files = list(
            self._output_files
        )

        return result

    def _acquire_spectrum(
        self,
        execution: StepExecutionContext,
    ) -> None:
        self._context.spectrum = (
            self._spectrum_analyzer
            .acquire_spectrum(
                timeout_s=execution.remaining_s,
                cancel_check=execution.cancel_check,
            )
        )

    def _acquire_delay(
        self,
        execution: StepExecutionContext,
    ) -> None:
        self._context.delay = (
            self._oscilloscope
            .acquire_delay()
        )

    def _acquire_cycle_count(
        self,
        execution: StepExecutionContext,
    ) -> None:
        self._context.cycle_count = (
            self._oscilloscope
            .acquire_cycle_count()
        )

    def _acquire_waveform(
        self,
        execution: StepExecutionContext,
    ) -> None:
        self._context.waveform = (
            self._oscilloscope
            .acquire_waveform()
        )

    def _save_result(
        self,
        execution: StepExecutionContext,
    ) -> None:
        if not self._context.is_complete:
            from instrument_capture_studio.core.exceptions import (
                CaptureStepError,
            )

            raise CaptureStepError(
                "save_result",
                "capture context is incomplete",
            )

        if self._current_job_id is None:
            raise RuntimeError(
                "current job id is not set"
            )

        output_files = self._result_sink.save(
            self._current_job_id,
            self._context,
        )

        self._output_files = list(
            output_files
        )

        self._context.metadata[
            "result_saved"
        ] = True
