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
    """Real training sample: FSW EXT+IMM plus two DSO-X acquisitions.

    The DSO-X data is intentionally split into two independent groups:

    - DELAY group: default timebase 500 ns/div, one DIGitize + DELAY + waveform.
    - CYCLE_COUNT group: default timebase 100 us/div, a second DIGitize + pulse
      count + a second waveform.

    FSW is armed before the DELAY group. That first DSO-X DIGitize is the
    hardware event expected to trigger the FSW EXT acquisition. The EXT trace
    is read before the second DSO-X acquisition so a second oscilloscope event
    cannot accidentally become part of the external-trigger sample.
    """

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
            CaptureStepDefinition("dsox_delay_group"),
            CaptureStepDefinition("fsw_ext_read", timeout_s=fsw_timeout_s),
            CaptureStepDefinition("dsox_cycle_group"),
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
            "dsox_delay_group": self._acquire_delay_group,
            "fsw_ext_read": self._read_ext,
            "dsox_cycle_group": self._acquire_cycle_group,
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
        result.metadata["schema_version"] = 1
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

    def _acquire_delay_group(self, execution: StepExecutionContext) -> None:
        delay, waveform = self._oscilloscope.acquire_delay_group()
        self._context.delay = delay
        self._context.waveform_delay = waveform
        self._context.metadata["waveform_channel"] = waveform.channel
        self._context.metadata["delay_timebase_scale_s"] = waveform.metadata.get(
            "timebase_scale_s"
        )

    def _read_ext(self, execution: StepExecutionContext) -> None:
        self._context.spectrum_ext = self._spectrum_analyzer.read_armed_spectrum(
            timeout_s=execution.remaining_s,
            cancel_check=execution.cancel_check,
            trigger_source="EXT",
        )

    def _acquire_cycle_group(self, execution: StepExecutionContext) -> None:
        cycle_count, waveform = self._oscilloscope.acquire_cycle_group()
        self._context.cycle_count = cycle_count
        self._context.waveform_cycle = waveform
        self._context.metadata["cycle_timebase_scale_s"] = waveform.metadata.get(
            "timebase_scale_s"
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
            raise CaptureStepError(
                "save_result",
                "paired capture requires EXT, IMM, DELAY waveform and CYCLE waveform",
            )
        if self._current_job_id is None:
            raise RuntimeError("current job id is not set")
        self._output_files = list(
            self._result_sink.save(self._current_job_id, self._context)
        )
        self._context.metadata["result_saved"] = True
