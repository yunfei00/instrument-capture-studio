from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True)
class StepExecutionContext:
    """单个 Capture Step 的执行时间约束。"""

    deadline: float | None = None

    @classmethod
    def from_timeout(
        cls,
        timeout_s: float | None,
    ) -> "StepExecutionContext":
        if timeout_s is None:
            return cls()

        return cls(
            deadline=monotonic() + timeout_s
        )

    @property
    def has_deadline(self) -> bool:
        return self.deadline is not None

    @property
    def remaining_s(self) -> float | None:
        if self.deadline is None:
            return None

        return max(
            0.0,
            self.deadline - monotonic(),
        )

    @property
    def expired(self) -> bool:
        remaining = self.remaining_s

        return (
            remaining is not None
            and remaining <= 0.0
        )
