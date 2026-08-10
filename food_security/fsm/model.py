"""Orchestrator for a single Food Security module run."""

from __future__ import annotations

from typing import TYPE_CHECKING

from food_security.fsm import pou
from food_security.fsm.allocator import AllocationResult, DietAllocator, StubAllocator
from food_security.fsm.errors import MissingCommodityData
from food_security.fsm.results import FoodSecurityResult, QuintileOutcome

if TYPE_CHECKING:
    from food_security.fsm.config import RunConfig
    from food_security.fsm.inputs import ModelInputs

_PERCENT = 100.0


class FoodSecurityModel:
    """Run the Food Security module for one (country, scenario, year)."""

    def __init__(
        self,
        inputs: ModelInputs,
        config: RunConfig,
        allocator: DietAllocator | None = None,
    ) -> None:
        """Store inputs, config, and the allocator (defaulting to the stub)."""
        self.inputs = inputs
        self.config = config
        self.allocator: DietAllocator = (
            allocator if allocator is not None else StubAllocator()
        )

    def run(self) -> FoodSecurityResult:
        """Execute the pipeline stages and return the result."""
        self._validate()
        self._build_availability()
        allocation = self._allocate()
        pou_by_quintile = self._compute_pou(allocation)
        return self._assemble(allocation, pou_by_quintile)

    def _validate(self) -> None:
        """Check invariants beyond field-level validation."""
        for commodity in self.inputs.commodities:
            if commodity.food_group is None:
                continue
            if commodity.code not in self.inputs.prices:
                msg = f"food commodity {commodity.code!r} has no price"
                raise MissingCommodityData(msg)

    def _build_availability(self) -> dict[str, float]:
        """Resolve the net availability mapping the allocator consumes."""
        # TODO: discarded by run() for now.  # noqa: TD002, TD003, FIX002
        # Once real net-availability resolution lands here, _allocate() must
        # be updated to pass the resolved mapping through instead of the raw
        # self.inputs it receives today.
        return dict(self.inputs.availability)

    def _allocate(self) -> AllocationResult:
        """Run the diet-allocation cascade via the pluggable allocator."""
        return self.allocator.allocate(self.inputs, self.config.weights)

    def _compute_pou(self, allocation: AllocationResult) -> dict[int, float]:
        """Compute per-quintile PoU fractions from the allocation's DEC values."""
        return {
            q.index: pou.pou_from_dec(allocation.dec[q.index], q.cv, q.mder)
            for q in self.inputs.quintiles
        }

    def _assemble(
        self,
        allocation: AllocationResult,
        pou_by_quintile: dict[int, float],
    ) -> FoodSecurityResult:
        """Build the final result, including the population-weighted PoU."""
        population_share = {
            q.index: q.population_share for q in self.inputs.quintiles
        }
        national = pou.national_pou(pou_by_quintile, population_share)
        outcomes = [
            QuintileOutcome(
                quintile=q.index,
                dec=allocation.dec[q.index],
                pou_percent=pou_by_quintile[q.index] * _PERCENT,
                penalized_diversity_per_year=(
                    allocation.penalized_diversity[q.index]
                ),
                penalized_sufficiency_per_year=(
                    allocation.penalized_sufficiency[q.index]
                ),
                income_for_food_percentage=(
                    allocation.income_for_food_fraction[q.index] * _PERCENT
                ),
            )
            for q in self.inputs.quintiles
        ]
        return FoodSecurityResult(
            country=self.inputs.country,
            scenario=self.inputs.scenario,
            year=self.inputs.year,
            per_quintile=outcomes,
            national_pou_percent=national * _PERCENT,
        )
