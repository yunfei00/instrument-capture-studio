from collections.abc import Callable
from copy import deepcopy

from instrument_capture_studio.adapters.formal_recipe import (
    FormalDSOXAdapter,
    FormalFSWAdapter,
)
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
    """Final synchronized FSW + DSO-X logical-sample workflow.

    The operator prepares the FSW measurement and Sweep Time before starting.
    Every physical acquisition is one-shot / Single.

    The original, hardware-qualified sequence remains unchanged:

    1. Read live FSW Sweep Time ``T``.
    2. Configure DSO-X sync window: Position=T/2, Scale=T/10.
    3. Switch FSW to EXT and ARM exactly one sweep (continuous OFF).
    4. Press DSO-X Single by SCPI, wait for that acquisition to finish, then
       read/save the first waveform. This hardware event triggers the FSW EXT
       sweep through the customer's trigger wiring.
    5. Read the completed FSW EXT spectrum from that one sweep.
    6. Configure the second DSO-X window from persisted GUI values.
    7. Press DSO-X Single again, wait for completion, then read/save the second
       independent waveform.
    8. Switch FSW to Free Run / IMM and acquire exactly one sweep.

    When the optional VIDEO spectrum is enabled, it is appended only after those
    four primary traces:

    9. Re-read live FSW Sweep Time ``Tv``.
    10. Set VIDEO trigger, manual VIDEO level, Trigger Offset=-Tv/2 and acquire
        one Single spectrum. The adapter restores the prior trigger state.
    11. Persist the original four primary traces plus the optional VIDEO trace.

    With VIDEO disabled, the step list and behavior remain the original v1.2
    nine-step workflow.
    """

    def __init__(
        self,
        spectrum_analyzer: FormalFSWAdapter,
        oscilloscope: FormalDSOXAdapter,
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
        self._sweep_time_s: float | None = None
        self._video_sweep_time_s: float | None = None
        self._video_enabled = bool(
            getattr(self._spectrum_analyzer, "video_trigger_enabled", False)
        )
        self._context = CaptureContext(metadata=deepcopy(self._initial_metadata))

        steps = [
            CaptureStepDefinition("fsw_sweep_time"),
            CaptureStepDefinition("dsox_sync_config"),
            CaptureStepDefinition("fsw_ext_arm"),
            CaptureStepDefinition("dsox_sync_capture"),
            CaptureStepDefinition("fsw_ext_read", timeout_s=fsw_timeout_s),
            CaptureStepDefinition("dsox_followup_config"),
            CaptureStepDefinition("dsox_followup_capture"),
            CaptureStepDefinition("fsw_freerun", timeout_s=fsw_timeout_s),
        ]
        if self._video_enabled:
            steps.extend(
                (
                    CaptureStepDefinition("fsw_video_sweep_time"),
                    CaptureStepDefinition("fsw_video_capture", timeout_s=fsw_timeout_s),
                )
            )
        steps.append(CaptureStepDefinition("save_result"))
        self._steps = tuple(steps)

    @property
    def steps(self) -> tuple[CaptureStepDefinition, ...]:
        return self._steps

    @property
    def context(self) -> CaptureContext:
        return self._context

    def run(self, job_id: str) -> CaptureResult:
        self._context = CaptureContext(metadata=deepcopy(self._initial_metadata))
        self._context.metadata["acquisition_modes"] = {
            "fsw_ext": "single",
            "dsox_sync": "single",
            "dsox_followup": "single",
            "fsw_freerun": "single",
        }
        if self._video_enabled:
            self._context.metadata["acquisition_modes"]["fsw_video"] = "single"
        self._context.metadata["fsw_video_enabled"] = self._video_enabled
        if self._video_enabled:
            self._context.metadata["fsw_video_level_pct_requested"] = float(
                getattr(self._spectrum_analyzer, "video_trigger_level_pct", 45.9)
            )

        self._current_job_id = job_id
        self._output_files = []
        self._sweep_time_s = None
        self._video_sweep_time_s = None

        raw_executors: dict[str, StepExecutor] = {
            "fsw_sweep_time": self._read_sweep_time,
            "dsox_sync_config": self._configure_sync_scope,
            "fsw_ext_arm": self._arm_ext,
            "dsox_sync_capture": self._capture_sync_scope,
            "fsw_ext_read": self._read_ext,
            "dsox_followup_config": self._configure_followup_scope,
            "dsox_followup_capture": self._capture_followup_scope,
            "fsw_freerun": self._acquire_freerun,
            "save_result": self._save_result,
        }
        if self._video_enabled:
            raw_executors["fsw_video_sweep_time"] = self._read_video_sweep_time
            raw_executors["fsw_video_capture"] = self._acquire_video

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
        result.metadata["acquisition_modes"] = deepcopy(
            self._context.metadata["acquisition_modes"]
        )
        result.metadata["fsw_video_enabled"] = self._video_enabled
        if "fsw_video_trigger" in self._context.metadata:
            result.metadata["fsw_video_trigger"] = deepcopy(
                self._context.metadata["fsw_video_trigger"]
            )
        if "instruments" in self._context.metadata:
            result.metadata["instruments"] = deepcopy(
                self._context.metadata["instruments"]
            )
        if "timing_windows" in self._context.metadata:
            result.metadata["timing_windows"] = deepcopy(
                self._context.metadata["timing_windows"]
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

    def _read_sweep_time(self, execution: StepExecutionContext) -> None:
        self._sweep_time_s = self._spectrum_analyzer.read_sweep_time_s()
        self._context.metadata["fsw_sweep_time_s"] = self._sweep_time_s

    def _configure_sync_scope(self, execution: StepExecutionContext) -> None:
        if self._sweep_time_s is None:
            raise RuntimeError("FSW Sweep Time has not been read")
        readback = self._oscilloscope.configure_sync_window(self._sweep_time_s)
        self._context.metadata.setdefault("timing_windows", {})["sync"] = readback

    def _arm_ext(self, execution: StepExecutionContext) -> None:
        self._spectrum_analyzer.arm_external_current_setup()

    def _capture_sync_scope(self, execution: StepExecutionContext) -> None:
        waveform = self._oscilloscope.acquire_sync_waveform(
            cancel_check=execution.cancel_check,
        )
        self._context.waveform_sync = waveform
        self._context.metadata["waveform_channel"] = waveform.channel

    def _read_ext(self, execution: StepExecutionContext) -> None:
        self._context.spectrum_ext = self._spectrum_analyzer.read_armed_spectrum(
            timeout_s=execution.remaining_s,
            cancel_check=execution.cancel_check,
            trigger_source="EXT",
        )

    def _configure_followup_scope(self, execution: StepExecutionContext) -> None:
        readback = self._oscilloscope.configure_followup_window()
        self._context.metadata.setdefault("timing_windows", {})["followup"] = readback

    def _capture_followup_scope(self, execution: StepExecutionContext) -> None:
        self._context.waveform_followup = (
            self._oscilloscope.acquire_followup_waveform(
                cancel_check=execution.cancel_check,
            )
        )

    def _acquire_freerun(self, execution: StepExecutionContext) -> None:
        self._context.spectrum_freerun = (
            self._spectrum_analyzer.acquire_freerun_current_setup(
                timeout_s=execution.remaining_s,
                cancel_check=execution.cancel_check,
            )
        )

    def _read_video_sweep_time(self, execution: StepExecutionContext) -> None:
        """Read Sweep Time again immediately before the optional VIDEO trace."""
        self._video_sweep_time_s = self._spectrum_analyzer.read_sweep_time_s()
        self._context.metadata["fsw_video_sweep_time_s"] = self._video_sweep_time_s
        self._context.metadata["fsw_video_trigger_offset_s_requested"] = (
            -self._video_sweep_time_s / 2.0
        )

    def _acquire_video(self, execution: StepExecutionContext) -> None:
        if self._video_sweep_time_s is None:
            raise RuntimeError("FSW VIDEO Sweep Time has not been read")
        video = self._spectrum_analyzer.acquire_video_current_setup(
            sweep_time_s=self._video_sweep_time_s,
            timeout_s=execution.remaining_s,
            cancel_check=execution.cancel_check,
        )
        self._context.spectrum_video = video
        trigger = video.metadata.get("video_trigger")
        if isinstance(trigger, dict):
            self._context.metadata["fsw_video_trigger"] = deepcopy(trigger)

    def _save_result(self, execution: StepExecutionContext) -> None:
        if not self._context.is_paired_complete:
            from instrument_capture_studio.core.exceptions import CaptureStepError

            raise CaptureStepError(
                "save_result",
                "paired capture requires EXT spectrum, sync waveform, "
                "follow-up waveform and Free Run spectrum",
            )
        if self._current_job_id is None:
            raise RuntimeError("current job id is not set")
        self._output_files = list(
            self._result_sink.save(self._current_job_id, self._context)
        )
        self._context.metadata["result_saved"] = True
