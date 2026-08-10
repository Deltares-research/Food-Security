"""Run configuration for the Food Security module."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from food_security.fsm.enums import AllocationDirection


class PenaltyWeights(BaseModel):
    """Soft-penalty weights for the diet-optimization objective.

    The per-quintile diet is chosen by minimizing food cost plus two soft
    penalties: one for falling short of the energy requirement (MDER) and one
    for violating the dietary-diversity bounds. These weights set how strongly
    each shortfall is penalized relative to money spent -- larger weights push
    the solution toward meeting energy/diversity even at higher cost.

    Note: `lambda_energy` has a principled lower bound (it must exceed the
    price of the cheapest available calories, else the model rationally
    chooses hunger). That floor is scenario-dependent and is expected to be
    derived at runtime by the real allocator; it is not enforced here.
    """

    lambda_energy: float = Field(
        ge=0,
        description="Penalty per unit of energy shortfall below MDER.",
    )
    lambda_diversity: float = Field(
        ge=0,
        description="Penalty per unit of dietary-diversity bound violation.",
    )


class RunConfig(BaseModel):
    """Settings controlling a single model run (one country/scenario/year).

    Holds the tuning knobs for the allocation step, kept separate from the
    data (`ModelInputs`) so the same inputs can be re-run under different
    optimization settings.
    """

    weights: PenaltyWeights = Field(
        description="Soft-penalty weights for the diet objective.",
    )
    allocation_direction: AllocationDirection = Field(
        default=AllocationDirection.RICHEST_FIRST,
        description=(
            "Order the cascade serves income groups. RICHEST_FIRST reproduces "
            "the paper: richer quintiles buy their diet first, the poorest get "
            "whatever food remains."
        ),
    )
    solver_options: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Free-form options forwarded verbatim to the LP solver the real "
            "allocator uses (e.g. tolerances, iteration caps). Valid keys "
            "depend on the chosen solver; unused by StubAllocator."
        ),
    )
