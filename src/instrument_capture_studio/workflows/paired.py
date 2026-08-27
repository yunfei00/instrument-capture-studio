from collections.abc import Callable
from copy import deepcopy

from instrument_capture_studio.adapters.dsox3034a import DSOX3034AAdapter
from instrument_capture_studio.adapters.fsw import FSWAdapter
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


class PairedCaptureWorkflow(CaptureWorkflow):
    """Real training-sample workflow: FSW EXT + DSO-X + paired FSW IMM."""

    def __init__(
        self,
        spectrum_analyzer: FSWAdapter,
        oscilloscope: DSOX3034AAdapter,
        *,
        fsw_timeout_s: float | None = None,
        cancel_check: CancelCheck | None = None,
        result_sink: CaptureResultSink | None = None,
        initial_metadata: dict[str, object] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self._spectrum_analyzer = spectrum_analyzer
        self._oscilloscope = oscilloscope
        self._cancel_check = cancel_check
        self._result_sink = result_sink or InMemoryResultSink()
        self._initial_metadata = deepcopy(initial_metadata or {})
        self._initial_metadata.setdefault("recipe", "ext_imm_pair")
        self._progress_callback = progress_callback
        self._current_job_id: str | None = None
        self._output_files: list[str] = []
        self._context = CaptureContext(metadata=deepcopy(self._initial_metadata))

        self._steps = (
            CaptureStepDefinition("fsw_ext_arm"),
            # acquire_waveform contains the DSO-X DIGitize call; keeping this
            # directly after ARM makes it the hardware EXT trigger point.
            CaptureStepDefinition("dsox_waveform"),
            CaptureStepDefinition("dsox_delay"),
            CaptureStepDefinition("dsox_cycle_count"),
            CaptureStepDefinition("fsw_ext_read", timeout_s=fsw_timeout_s),
            CaptureStepDefinition("fsw_imm", timeout_s=fsw_timeout_s),
            CaptureStepDefinition("save_result"),
        )

    @property
    def steps(self) -> tuple[CaptureStepDefinition, ...]:
        return self._steps

    @property
    def context(self) -> CaptureContext:
        return self._context

    def run(self, job_id: str) -> CaptureResult:
        self._context = CaptureContext(metadata=deepcopy(self._initial_metadata))
        self._current_job_id = job_id
        self._output_files = []

        raw_executors: dict[str, StepExecutor] = {
            "fsw_ext_arm": self._arm_ext,
            "dsox_waveform": self._acquire_waveform,
            "dsox_delay": self._acquire_delay,
            "dsox_cycle_count": self._acquire_cycle_count,
            "fsw_ext_read": self._read_ext,
            "fsw_imm": self._acquire_imm,
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
        result.metadata["schema_version"] = 2
        result.metadata["recipe"] = "ext_imm_pair"
        result.metadata["capture_complete"] = self._context.is_paired_complete
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
            self._notify_progress(step_name, "running", index)
            try:
                executor(execution)
            except Exception:
                self._notify_progress(step_name, "failed", index)
                raise
            else:
                self._notify_progress(step_name, "succeeded", index + 1)
        return wrapped

    def _notify_progress(self, step_name: str, state: str, completed: int) -> None:
        if self._progress_callback is None:
            return
        try:
            self._progress_callback(step_name, state, completed, len(self.steps))
        except Exception:
            return

    def _arm_ext(self, execution: StepExecutionContext) -> None:
        self._spectrum_analyzer.arm_spectrum("EXT")

    def _acquire_waveform(self, execution: StepExecutionContext) -> None:
        self._context.waveform = self._oscilloscope.acquire_waveform()
        self._context.metadata["waveform_channel"] = self._context.waveform.channel

    def _acquire_delay(self, execution: StepExecutionContext) -> None:
        self._context.delay = self._oscilloscope.acquire_delay()

    def _acquire_cycle_count(self, execution: StepExecutionContext) -> None:
        self._context.cycle_count = self._oscilloscope.acquire_cycle_count()

    def _read_ext(self, execution: StepExecutionContext) -> None:
        self._context.spectrum_ext = self._spectrum_analyzer.read_armed_spectrum(
            timeout_s=execution.remaining_s,
            cancel_check=execution.cancel_check,
            trigger_source="EXT",
        )

    def _acquire_imm(self, execution: StepExecutionContext) -> None:
        self._context.spectrum_imm = (
            self._spectrum_analyzer.acquire_spectrum_with_trigger(
                "IMM",
                timeout_s=execution.remaining_s,
                cancel_check=execution.cancel_check,
            )
        )

    def _save_result(self, execution: StepExecutionContext) -> None:
        if not self._context.is_paired_complete:
            from instrument_capture_studio.core.exceptions import CaptureStepError
            raise CaptureStepError("save_result", "paired capture context is incomplete")
        if self._current_job_id is None:
            raise RuntimeError("current job id is not set")
        self._output_files = list(
            self._result_sink.save(self._current_job_id, self._context)
        )
        self._context.metadata["result_saved"] = True
