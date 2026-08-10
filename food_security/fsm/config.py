"""Run configuration for the Food Security module."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from food_security.fsm.enums import AllocationDirection


class PenaltyWeights(BaseModel):
    """Soft-penalty weights for the diet objective.

    Note: `lambda_energy` has a principled lower bound (it must exceed the
    price of the cheapest available calories, else the model rationally
    chooses hunger). That floor is scenario-dependent and is expected to be
    derived at runtime by the real allocator; it is not enforced here.
    """

    lambda_energy: float = Field(ge=0)
    lambda_diversity: float = Field(ge=0)


class RunConfig(BaseModel):
    """Settings controlling a single model run."""

    weights: PenaltyWeights
    allocation_direction: AllocationDirection = AllocationDirection.RICHEST_FIRST
    solver_options: dict[str, Any] = Field(default_factory=dict)
