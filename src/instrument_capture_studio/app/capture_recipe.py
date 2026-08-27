from dataclasses import dataclass
from enum import Enum


class CaptureRecipe(str, Enum):
    """What one logical training sample contains."""

    EXT_IMM_PAIR = "ext_imm_pair"
    IMM_SPECTRUM_ONLY = "imm_spectrum_only"
    DSOX_ONLY = "dsox_only"


class ExecutionMode(str, Enum):
    """How a selected recipe is repeated."""

    SINGLE = "single"
    FREQUENCY_SWEEP = "frequency_sweep"
    FIXED_REPEAT = "fixed_repeat"


@dataclass(frozen=True)
class CapturePlanDescriptor:
    recipe: CaptureRecipe
    execution_mode: ExecutionMode

    @property
    def requires_fsw(self) -> bool:
        return self.recipe in {
            CaptureRecipe.EXT_IMM_PAIR,
            CaptureRecipe.IMM_SPECTRUM_ONLY,
        }

    @property
    def requires_dsox(self) -> bool:
        return self.recipe in {
            CaptureRecipe.EXT_IMM_PAIR,
            CaptureRecipe.DSOX_ONLY,
        }
