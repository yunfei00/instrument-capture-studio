from collections.abc import Callable
from datetime import datetime, timezone

from instrument_capture_studio.core.models import (
    CaptureResult,
    JobState,
    StepResult,
    StepState,
)
from instrument_capture_studio.workflows.base import (
    CaptureStepDefinition,
    CaptureWorkflow,
)


StepExecutor = Callable[[], None]
CancelCheck = Callable[[], bool]


class SequentialWorkflowRunner(CaptureWorkflow):
    """按照定义顺序依次执行 Capture Step。"""

    def __init__(
        self,
        steps: tuple[CaptureStepDefinition, ...],
        executors: dict[str, StepExecutor],
        cancel_check: CancelCheck | None = None,
    ):
        self._steps = steps
        self._executors = executors
        self._cancel_check = cancel_check or (lambda: False)

        missing = [
            step.name
            for step in steps
            if step.name not in executors
        ]

        if missing:
            raise ValueError(
                f"missing step executors: {', '.join(missing)}"
            )

    @property
    def steps(self) -> tuple[CaptureStepDefinition, ...]:
        return self._steps

    def run(self, job_id: str) -> CaptureResult:
        result = CaptureResult(
            job_id=job_id,
            state=JobState.RUNNING,
            started_at=datetime.now(timezone.utc),
            steps=[
                StepResult(name=step.name)
                for step in self.steps
            ],
        )

        for index, definition in enumerate(self.steps):
            step_result = result.steps[index]

            if self._cancel_check():
                step_result.state = StepState.CANCELED
                self._skip_remaining(result, index + 1)

                result.state = JobState.CANCELED
                result.finished_at = datetime.now(timezone.utc)
                return result

            step_result.state = StepState.RUNNING
            step_result.started_at = datetime.now(timezone.utc)

            attempts = 0

            while attempts <= definition.max_retries:
                attempts += 1

                try:
                    self._executors[definition.name]()

                    step_result.state = StepState.SUCCEEDED
                    step_result.metadata["attempts"] = attempts
                    step_result.finished_at = datetime.now(timezone.utc)
                    break

                except Exception as exc:
                    if attempts > definition.max_retries:
                        step_result.state = StepState.FAILED
                        step_result.error = str(exc)
                        step_result.metadata["attempts"] = attempts
                        step_result.finished_at = datetime.now(timezone.utc)

                        self._skip_remaining(result, index + 1)

                        result.state = JobState.FAILED
                        result.finished_at = datetime.now(timezone.utc)
                        return result

        result.state = JobState.SUCCEEDED
        result.finished_at = datetime.now(timezone.utc)
        return result

    @staticmethod
    def _skip_remaining(
        result: CaptureResult,
        start_index: int,
    ) -> None:
        for step in result.steps[start_index:]:
            step.state = StepState.SKIPPED
