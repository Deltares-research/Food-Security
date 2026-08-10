"""Tests for fsm input models and their validators."""

import pytest
from pydantic import ValidationError

from food_security.fsm.enums import FoodGroup
from food_security.fsm.inputs import (
    Commodity,
    DietRequirements,
    ModelInputs,
    Quintile,
    ShareBounds,
    SupplyComponents,
)


def _commodity(code="RICE", group=FoodGroup.CARBS) -> Commodity:
    return Commodity(
        code=code, name=code.title(), food_group=group, energy_kcal_per_kg=1300.0,
    )


def _quintiles() -> list[Quintile]:
    return [
        Quintile(
            index=i,
            food_budget_per_capita_day=20.0,
            population_share=0.2,
            cv=0.3,
            mder=1806.61,
        )
        for i in range(1, 6)
    ]


def _diet() -> DietRequirements:
    return DietRequirements(
        group_bounds={FoodGroup.CARBS: ShareBounds(min=0.55, max=0.75)},
    )


def _inputs(**overrides: object) -> ModelInputs:
    base = {
        "country": "Egypt",
        "scenario": "ssp2",
        "year": 2020,
        "commodities": [_commodity()],
        "availability": {"RICE": 1000.0},
        "prices": {"RICE": 250.0},
        "quintiles": _quintiles(),
        "diet": _diet(),
    }
    base.update(overrides)
    return ModelInputs(**base)


def test_valid_inputs_construct():
    inp = _inputs()
    assert inp.availability["RICE"] == 1000.0
    assert len(inp.quintiles) == 5


def test_share_bounds_rejects_min_gt_max():
    with pytest.raises(ValidationError):
        ShareBounds(min=0.8, max=0.5)


def test_commodity_rejects_negative_energy():
    with pytest.raises(ValidationError):
        Commodity(code="X", name="X", energy_kcal_per_kg=-1.0)


def test_supply_components_net_clamps_at_zero():
    sc = SupplyComponents(production_delta=10.0, exports=25.0)
    assert sc.net() == 0.0
    sc2 = SupplyComponents(production_delta=30.0, imports=5.0, exports=10.0)
    assert sc2.net() == 25.0


def test_inputs_reject_duplicate_commodity_codes():
    with pytest.raises(ValidationError):
        _inputs(commodities=[_commodity(), _commodity()])


def test_inputs_reject_unknown_availability_key():
    with pytest.raises(ValidationError):
        _inputs(availability={"MAIZE": 5.0})


def test_inputs_reject_negative_availability():
    with pytest.raises(ValidationError):
        _inputs(availability={"RICE": -5.0})


def test_inputs_reject_population_share_not_summing_to_one():
    bad = _quintiles()
    bad[0] = Quintile(
        index=1,
        food_budget_per_capita_day=20.0,
        population_share=0.5,
        cv=0.3,
        mder=1806.61,
    )
    with pytest.raises(ValidationError):
        _inputs(quintiles=bad)


def test_inputs_reject_duplicate_quintile_index():
    q = _quintiles()
    q[1] = Quintile(
        index=1,
        food_budget_per_capita_day=20.0,
        population_share=0.2,
        cv=0.3,
        mder=1806.61,
    )
    with pytest.raises(ValidationError):
        _inputs(quintiles=q)


def test_inputs_reject_quintiles_not_covering_1_to_5() -> None:
    quints = [
        Quintile(
            index=i,
            food_budget_per_capita_day=20.0,
            population_share=0.25,
            cv=0.3,
            mder=1806.61,
        )
        for i in (1, 2, 3, 4)
    ]
    with pytest.raises(ValidationError):
        _inputs(quintiles=quints)
