from collections.abc import Callable
from copy import deepcopy

from instrument_capture_studio.adapters.interfaces import (
    OscilloscopeAdapter,
    SpectrumAnalyzerAdapter,
)
from instrument_capture_studio.core.models import CaptureResult
from instrument_capture_studio.workflows.base import (
    CaptureStepDefinition,
    CaptureWorkflow,
)
from instrument_capture_studio.workflows.context import CaptureContext
from instrument_capture_studio.workflows.execution import StepExecutionContext
from instrument_capture_studio.workflows.runner import SequentialWorkflowRunner
from instrument_capture_studio.workflows.result_sink import (
    CaptureResultSink,
    InMemoryResultSink,
)


CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[str, str, int, int], None]
StepExecutor = Callable[[StepExecutionContext], None]


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
        initial_metadata: dict[str, object] | None = None,
        progress_callback: ProgressCallback | None = None,
    ):
        self._spectrum_analyzer = spectrum_analyzer
        self._oscilloscope = oscilloscope
        self._cancel_check = cancel_check
        self._result_sink = result_sink or InMemoryResultSink()
        self._initial_metadata = deepcopy(initial_metadata or {})
        self._progress_callback = progress_callback

        self._current_job_id: str | None = None
        self._output_files: list[str] = []

        self._steps = (
            CaptureStepDefinition(
                "fsw_spectrum",
                timeout_s=fsw_timeout_s,
            ),
            CaptureStepDefinition("dsox_delay"),
            CaptureStepDefinition("dsox_cycle_count"),
            CaptureStepDefinition("dsox_waveform"),
            CaptureStepDefinition("save_result"),
        )

        self._context = CaptureContext(
            metadata=deepcopy(self._initial_metadata)
        )

    @property
    def steps(self) -> tuple[CaptureStepDefinition, ...]:
        return self._steps

    @property
    def context(self) -> CaptureContext:
        return self._context

    def run(self, job_id: str) -> CaptureResult:
        # Workflow 对象允许重复使用；每个新 Job 必须从全新的上下文开始。
        self._context = CaptureContext(
            metadata=deepcopy(self._initial_metadata)
        )
        self._current_job_id = job_id
        self._output_files = []

        raw_executors: dict[str, StepExecutor] = {
            "fsw_spectrum": self._acquire_spectrum,
            "dsox_delay": self._acquire_delay,
            "dsox_cycle_count": self._acquire_cycle_count,
            "dsox_waveform": self._acquire_waveform,
            "save_result": self._save_result,
        }

        executors = {
            definition.name: self._with_progress(
                definition.name,
                index,
                raw_executors[definition.name],
            )
            for index, definition in enumerate(self.steps)
        }

        runner = SequentialWorkflowRunner(
            steps=self.steps,
            executors=executors,
            cancel_check=self._cancel_check,
        )

        result = runner.run(job_id)

        result.metadata["capture_complete"] = self._context.is_complete
        result.metadata["result_saved"] = bool(
            self._context.metadata.get("result_saved", False)
        )

        if "instruments" in self._context.metadata:
            result.metadata["instruments"] = deepcopy(
                self._context.metadata["instruments"]
            )

        result.output_files = list(self._output_files)
        return result

    def _with_progress(
        self,
        step_name: str,
        index: int,
        executor: StepExecutor,
    ) -> StepExecutor:
        def wrapped(execution: StepExecutionContext) -> None:
            self._notify_progress(
                step_name,
                "running",
                index,
            )

            try:
                executor(execution)
            except Exception:
                self._notify_progress(
                    step_name,
                    "failed",
                    index,
                )
                raise
            else:
                self._notify_progress(
                    step_name,
                    "succeeded",
                    index + 1,
                )

        return wrapped

    def _notify_progress(
        self,
        step_name: str,
        state: str,
        completed_steps: int,
    ) -> None:
        callback = self._progress_callback
        if callback is None:
            return

        # UI/observer 回调不能影响仪表采集主流程。
        try:
            callback(
                step_name,
                state,
                completed_steps,
                len(self.steps),
            )
        except Exception:
            return

    def _acquire_spectrum(
        self,
        execution: StepExecutionContext,
    ) -> None:
        self._context.spectrum = self._spectrum_analyzer.acquire_spectrum(
            timeout_s=execution.remaining_s,
            cancel_check=execution.cancel_check,
        )

    def _acquire_delay(
        self,
        execution: StepExecutionContext,
    ) -> None:
        self._context.delay = self._oscilloscope.acquire_delay()

    def _acquire_cycle_count(
        self,
        execution: StepExecutionContext,
    ) -> None:
        self._context.cycle_count = self._oscilloscope.acquire_cycle_count()

    def _acquire_waveform(
        self,
        execution: StepExecutionContext,
    ) -> None:
        self._context.waveform = self._oscilloscope.acquire_waveform()

    def _save_result(
        self,
        execution: StepExecutionContext,
    ) -> None:
        if not self._context.is_complete:
            from instrument_capture_studio.core.exceptions import CaptureStepError

            raise CaptureStepError(
                "save_result",
                "capture context is incomplete",
            )

        if self._current_job_id is None:
            raise RuntimeError("current job id is not set")

        output_files = self._result_sink.save(
            self._current_job_id,
            self._context,
        )
        self._output_files = list(output_files)
        self._context.metadata["result_saved"] = True
