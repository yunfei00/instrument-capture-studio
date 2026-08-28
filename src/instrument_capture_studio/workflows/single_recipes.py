from collections.abc import Callable
from copy import deepcopy

from instrument_capture_studio.core.models import CaptureResult
from instrument_capture_studio.workflows.base import CaptureStepDefinition, CaptureWorkflow
from instrument_capture_studio.workflows.context import CaptureContext
from instrument_capture_studio.workflows.execution import StepExecutionContext
from instrument_capture_studio.workflows.result_sink import (
    CaptureResultSink,
    InMemoryResultSink,
)
from instrument_capture_studio.workflows.runner import SequentialWorkflowRunner


CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[str, str, int, int], None]
StepExecutor = Callable[[StepExecutionContext], None]


class _RecipeWorkflowBase(CaptureWorkflow):
    recipe = ""

    def __init__(
        self,
        *,
        cancel_check: CancelCheck | None = None,
        result_sink: CaptureResultSink | None = None,
        initial_metadata: dict[str, object] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self._cancel_check = cancel_check
        self._result_sink = result_sink or InMemoryResultSink()
        self._initial_metadata = deepcopy(initial_metadata or {})
        self._initial_metadata.setdefault("recipe", self.recipe)
        self._progress_callback = progress_callback
        self._current_job_id: str | None = None
        self._output_files: list[str] = []
        self._context = CaptureContext(metadata=deepcopy(self._initial_metadata))

    @property
    def context(self) -> CaptureContext:
        return self._context

    def _run_steps(
        self,
        job_id: str,
        steps: tuple[CaptureStepDefinition, ...],
        raw_executors: dict[str, StepExecutor],
    ) -> CaptureResult:
        self._context = CaptureContext(metadata=deepcopy(self._initial_metadata))
        self._current_job_id = job_id
        self._output_files = []
        executors = {
            definition.name: self._with_progress(
                definition.name,
                index,
                len(steps),
                raw_executors[definition.name],
            )
            for index, definition in enumerate(steps)
        }
        result = SequentialWorkflowRunner(
            steps=steps,
            executors=executors,
            cancel_check=self._cancel_check,
        ).run(job_id)
        result.metadata["recipe"] = self.recipe
        result.metadata["schema_version"] = 1
        result.metadata["capture_complete"] = self._context.capture_complete
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
        step_count: int,
        executor: StepExecutor,
    ) -> StepExecutor:
        def wrapped(execution: StepExecutionContext) -> None:
            self._notify(step_name, "running", index, step_count)
            try:
                executor(execution)
            except Exception:
                self._notify(step_name, "failed", index, step_count)
                raise
            else:
                self._notify(step_name, "succeeded", index + 1, step_count)
        return wrapped

    def _notify(self, name: str, state: str, completed: int, count: int) -> None:
        if self._progress_callback is None:
            return
        try:
            self._progress_callback(name, state, completed, count)
        except Exception:
            return

    def _save(self, execution: StepExecutionContext) -> None:
        if not self._context.capture_complete:
            from instrument_capture_studio.core.exceptions import CaptureStepError

            raise CaptureStepError(
                "save_result",
                f"{self.recipe} context is incomplete",
            )
        if self._current_job_id is None:
            raise RuntimeError("current job id is not set")
        self._output_files = list(
            self._result_sink.save(self._current_job_id, self._context)
        )
        self._context.metadata["result_saved"] = True


class ImmSpectrumOnlyWorkflow(_RecipeWorkflowBase):
    recipe = "imm_spectrum_only"

    def __init__(
        self,
        spectrum_analyzer,
        *,
        fsw_timeout_s: float | None = None,
        cancel_check: CancelCheck | None = None,
        result_sink: CaptureResultSink | None = None,
        initial_metadata: dict[str, object] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        super().__init__(
            cancel_check=cancel_check,
            result_sink=result_sink,
            initial_metadata=initial_metadata,
            progress_callback=progress_callback,
        )
        self._spectrum_analyzer = spectrum_analyzer
        self._fsw_timeout_s = fsw_timeout_s

    @property
    def steps(self) -> tuple[CaptureStepDefinition, ...]:
        return (
            CaptureStepDefinition("fsw_imm", timeout_s=self._fsw_timeout_s),
            CaptureStepDefinition("save_result"),
        )

    def run(self, job_id: str) -> CaptureResult:
        return self._run_steps(
            job_id,
            self.steps,
            {"fsw_imm": self._acquire, "save_result": self._save},
        )

    def _acquire(self, execution: StepExecutionContext) -> None:
        self._context.spectrum_imm = (
            self._spectrum_analyzer.acquire_spectrum_with_trigger(
                "IMM",
                timeout_s=execution.remaining_s,
                cancel_check=execution.cancel_check,
            )
        )


class DSOXOnlyWorkflow(_RecipeWorkflowBase):
    recipe = "dsox_only"

    def __init__(
        self,
        oscilloscope,
        *,
        cancel_check: CancelCheck | None = None,
        result_sink: CaptureResultSink | None = None,
        initial_metadata: dict[str, object] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        super().__init__(
            cancel_check=cancel_check,
            result_sink=result_sink,
            initial_metadata=initial_metadata,
            progress_callback=progress_callback,
        )
        self._oscilloscope = oscilloscope

    @property
    def steps(self) -> tuple[CaptureStepDefinition, ...]:
        return (
            CaptureStepDefinition("dsox_delay_group"),
            CaptureStepDefinition("dsox_cycle_group"),
            CaptureStepDefinition("save_result"),
        )

    def run(self, job_id: str) -> CaptureResult:
        # Do not silently rewrite the oscilloscope trigger/acquisition settings
        # in this workflow. A previous timeout investigation showed the actual
        # failure was caused by a USB-to-TCP bridge converting binary waveform
        # traffic as ASCII. Product capture should therefore preserve the
        # configured DSO-X behavior and let the transport path remain binary
        # transparent.
        return self._run_steps(
            job_id,
            self.steps,
            {
                "dsox_delay_group": self._acquire_delay_group,
                "dsox_cycle_group": self._acquire_cycle_group,
                "save_result": self._save,
            },
        )

    def _acquire_delay_group(self, execution: StepExecutionContext) -> None:
        delay, waveform = self._oscilloscope.acquire_delay_group()
        self._context.delay = delay
        self._context.waveform_delay = waveform
        self._context.metadata["waveform_channel"] = waveform.channel
        self._context.metadata["delay_timebase_scale_s"] = waveform.metadata.get(
            "timebase_scale_s"
        )

    def _acquire_cycle_group(self, execution: StepExecutionContext) -> None:
        cycle_count, waveform = self._oscilloscope.acquire_cycle_group()
        self._context.cycle_count = cycle_count
        self._context.waveform_cycle = waveform
        self._context.metadata["cycle_timebase_scale_s"] = waveform.metadata.get(
            "timebase_scale_s"
        )
