from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic


CancelCheck = Callable[[], bool]


@dataclass(frozen=True)
class StepExecutionContext:
    """单个 Capture Step 的执行约束。"""

    deadline: float | None = None
    cancel_check: CancelCheck | None = None
    timeout_s: float | None = None

    @classmethod
    def from_timeout(
        cls,
        timeout_s: float | None,
        *,
        cancel_check: CancelCheck | None = None,
    ) -> "StepExecutionContext":
        if timeout_s is None:
            return cls(
                cancel_check=cancel_check,
            )

        return cls(
            deadline=monotonic() + timeout_s,
            cancel_check=cancel_check,
            timeout_s=timeout_s,
        )

    @property
    def has_deadline(self) -> bool:
        return self.deadline is not None

    @property
    def remaining_s(self) -> float | None:
        if self.deadline is None:
            return None

        remaining = max(
            0.0,
            self.deadline - monotonic(),
        )

        # Floating-point arithmetic on a large monotonic clock value can make
        # `deadline - now` exceed the configured timeout by a few ulps. Never
        # pass an instrument a timeout larger than the user's configured limit.
        if self.timeout_s is not None:
            return min(remaining, self.timeout_s)

        return remaining

    @property
    def expired(self) -> bool:
        remaining = self.remaining_s

        return (
            remaining is not None
            and remaining <= 0.0
        )

    @property
    def canceled(self) -> bool:
        if self.cancel_check is None:
            return False

        return bool(
            self.cancel_check()
        )
