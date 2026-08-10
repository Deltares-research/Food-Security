"""Tests for the allocator seam and the stub implementation."""

from food_security.fsm.allocator import (
    AllocationResult,
    DietAllocator,
    StubAllocator,
)
from food_security.fsm.config import PenaltyWeights
from food_security.fsm.enums import FoodGroup
from food_security.fsm.inputs import (
    Commodity,
    DietRequirements,
    ModelInputs,
    Quintile,
    ShareBounds,
)


def _inputs() -> ModelInputs:
    return ModelInputs(
        country="Egypt",
        scenario="ssp2",
        year=2020,
        commodities=[
            Commodity(
                code="RICE",
                name="Rice",
                food_group=FoodGroup.CARBS,
                energy_kcal_per_kg=1300.0,
            ),
        ],
        availability={"RICE": 1000.0},
        prices={"RICE": 250.0},
        quintiles=[
            Quintile(
                index=i,
                food_budget_per_capita_day=20.0,
                population_share=0.2,
                cv=0.3,
                mder=1806.61,
            )
            for i in range(1, 6)
        ],
        diet=DietRequirements(
            group_bounds={FoodGroup.CARBS: ShareBounds(min=0.55, max=0.75)},
        ),
    )


def test_stub_satisfies_protocol():
    assert isinstance(StubAllocator(), DietAllocator)


def test_stub_returns_dec_equal_to_mder_and_zero_penalties():
    inp = _inputs()
    result = StubAllocator().allocate(
        inp, PenaltyWeights(lambda_energy=1.0, lambda_diversity=1.0),
    )
    assert isinstance(result, AllocationResult)
    for q in inp.quintiles:
        assert result.dec[q.index] == q.mder
        assert result.penalized_sufficiency[q.index] == 0.0
        assert result.penalized_diversity[q.index] == 0.0
        assert result.income_for_food_fraction[q.index] == 0.0
        assert result.consumption[q.index] == {}
