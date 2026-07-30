"""Tests for the FoodSecurityModel orchestrator."""

import pytest

from food_security.fsm.config import PenaltyWeights, RunConfig
from food_security.fsm.enums import FoodGroup
from food_security.fsm.errors import MissingCommodityData
from food_security.fsm.inputs import (
    Commodity,
    DietRequirements,
    ModelInputs,
    Quintile,
    ShareBounds,
)
from food_security.fsm.model import FoodSecurityModel
from food_security.fsm.results import FoodSecurityResult


def _inputs(**overrides: object) -> ModelInputs:
    base = {
        "country": "Egypt",
        "scenario": "ssp2",
        "year": 2020,
        "commodities": [
            Commodity(
                code="RICE",
                name="Rice",
                food_group=FoodGroup.CARBS,
                energy_kcal_per_kg=1300.0,
            ),
        ],
        "availability": {"RICE": 1000.0},
        "prices": {"RICE": 250.0},
        "quintiles": [
            Quintile(
                index=i,
                food_budget_per_capita_day=20.0,
                population_share=0.2,
                cv=0.3,
                mder=1806.61,
            )
            for i in range(1, 6)
        ],
        "diet": DietRequirements(
            group_bounds={FoodGroup.CARBS: ShareBounds(min=0.55, max=0.75)},
        ),
    }
    base.update(overrides)
    return ModelInputs(**base)


def _config() -> RunConfig:
    return RunConfig(
        weights=PenaltyWeights(lambda_energy=1.0, lambda_diversity=1.0),
    )


def test_run_produces_result_for_every_quintile():
    result = FoodSecurityModel(_inputs(), _config()).run()
    assert isinstance(result, FoodSecurityResult)
    assert {o.quintile for o in result.per_quintile} == {1, 2, 3, 4, 5}
    assert 0.0 <= result.national_pou_percent <= 100.0


def test_run_output_records_match_schema_keys():
    result = FoodSecurityModel(_inputs(), _config()).run()
    keys = set(result.to_records()[0])
    assert keys == {
        "scenario",
        "quintile",
        "pou_percent",
        "penalized_diversity_per_year",
        "penalized_sufficiency_per_year",
        "income_for_food_percentage",
    }


def test_run_rejects_food_commodity_without_price():
    inp = _inputs(prices={})
    with pytest.raises(MissingCommodityData):
        FoodSecurityModel(inp, _config()).run()
