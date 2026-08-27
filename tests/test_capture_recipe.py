from instrument_capture_studio.app.capture_recipe import (
    CapturePlanDescriptor,
    CaptureRecipe,
    ExecutionMode,
)


def test_recipe_instrument_requirements():
    paired = CapturePlanDescriptor(
        CaptureRecipe.EXT_IMM_PAIR,
        ExecutionMode.FREQUENCY_SWEEP,
    )
    assert paired.requires_fsw is True
    assert paired.requires_dsox is True

    imm_only = CapturePlanDescriptor(
        CaptureRecipe.IMM_SPECTRUM_ONLY,
        ExecutionMode.SINGLE,
    )
    assert imm_only.requires_fsw is True
    assert imm_only.requires_dsox is False

    dsox_only = CapturePlanDescriptor(
        CaptureRecipe.DSOX_ONLY,
        ExecutionMode.FIXED_REPEAT,
    )
    assert dsox_only.requires_fsw is False
    assert dsox_only.requires_dsox is True
