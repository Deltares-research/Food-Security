"""Typed interface for the Food Security module (national per-quintile model).

Construct `ModelInputs` + `RunConfig`, pass them to `FoodSecurityModel`, and call
`run()` to get a `FoodSecurityResult`. The diet allocator is pluggable; `StubAllocator`
is used by default so the pipeline runs before the real LP exists.
"""

from food_security.fsm.allocator import (
    AllocationResult,
    DietAllocator,
    StubAllocator,
)
from food_security.fsm.config import PenaltyWeights, RunConfig
from food_security.fsm.enums import AllocationDirection, FoodGroup
from food_security.fsm.errors import (
    FSMError,
    InfeasibleAllocation,
    MissingCommodityData,
)
from food_security.fsm.inputs import (
    Commodity,
    DietRequirements,
    ModelInputs,
    Quintile,
    ShareBounds,
    SupplyComponents,
)
from food_security.fsm.model import FoodSecurityModel
from food_security.fsm.results import FoodSecurityResult, QuintileOutcome

__all__ = [
    "AllocationDirection",
    "AllocationResult",
    "Commodity",
    "DietAllocator",
    "DietRequirements",
    "FSMError",
    "FoodGroup",
    "FoodSecurityModel",
    "FoodSecurityResult",
    "InfeasibleAllocation",
    "MissingCommodityData",
    "ModelInputs",
    "PenaltyWeights",
    "Quintile",
    "QuintileOutcome",
    "RunConfig",
    "ShareBounds",
    "StubAllocator",
    "SupplyComponents",
]
