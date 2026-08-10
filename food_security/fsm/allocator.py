"""Diet-allocation seam: the pluggable optimizer interface and a runnable stub."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from food_security.fsm.config import PenaltyWeights
    from food_security.fsm.inputs import ModelInputs


class AllocationResult(BaseModel):
    """Per-quintile results of the diet-allocation cascade.

    Every field is keyed by quintile index (1..5). `dec` is the input the PoU
    calculation consumes; the rest are reported through to the output. All raw
    fractions/rates here are unscaled (not yet multiplied to percentages).
    """

    consumption: dict[int, dict[str, float]] = Field(
        default_factory=dict,
        description=(
            "Chosen per-capita diet: {quintile: {commodity code: quantity}}."
        ),
    )
    dec: dict[int, float] = Field(
        description=(
            "Dietary Energy Consumption per quintile (kcal/capita/day): the "
            "mean energy intake achieved by the allocated diet. Feeds PoU."
        ),
    )
    penalized_sufficiency: dict[int, float] = Field(
        description="Energy-shortfall penalty term per quintile (objective cost).",
    )
    penalized_diversity: dict[int, float] = Field(
        description="Diversity-violation penalty term per quintile (objective cost).",
    )
    income_for_food_fraction: dict[int, float] = Field(
        description=(
            "Share of income the quintile must spend to afford its diet, as a "
            "fraction (0-1)."
        ),
    )


@runtime_checkable
class DietAllocator(Protocol):
    """Allocates available food across income quintiles (richest first).

    Implementations own the Q5->Q1 cascade and the per-quintile least-cost diet LP,
    including unit reconciliation. In particular: availability is per person nationally,
    but a quintile's consumption is per person within that quintile (~20% of the
    population), so a quintile consuming `C` per capita draws `population_share * C`
    from the national pool.
    """

    def allocate(
        self,
        inputs: ModelInputs,
        weights: PenaltyWeights,
    ) -> AllocationResult:
        """Allocate food across quintiles and return per-quintile outcomes."""
        ...


class StubAllocator:
    """Deterministic placeholder allocator: DEC = MDER, zero penalties, no consumption.

    Lets the whole pipeline run end-to-end before the real LP exists. Note that DEC =
    MDER makes downstream PoU land near 55% — an artifact of pinning DEC at the
    requirement, not a real result.
    """

    def allocate(
        self,
        inputs: ModelInputs,
        weights: PenaltyWeights,  # noqa: ARG002 - part of the protocol signature
    ) -> AllocationResult:
        """Return a well-formed dummy allocation for every quintile."""
        dec = {q.index: q.mder for q in inputs.quintiles}
        zeros = {q.index: 0.0 for q in inputs.quintiles}
        consumption: dict[int, dict[str, float]] = {
            q.index: {} for q in inputs.quintiles
        }
        return AllocationResult(
            consumption=consumption,
            dec=dec,
            penalized_sufficiency=dict(zeros),
            penalized_diversity=dict(zeros),
            income_for_food_fraction=dict(zeros),
        )
