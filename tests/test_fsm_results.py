"""Tests for fsm result models."""

from food_security.fsm.results import FoodSecurityResult, QuintileOutcome


def _result() -> FoodSecurityResult:
    return FoodSecurityResult(
        country="Egypt",
        scenario="ssp2",
        year=2020,
        per_quintile=[
            QuintileOutcome(
                quintile=1,
                dec=1806.61,
                pou_percent=55.0,
                penalized_diversity_per_year=0.0,
                penalized_sufficiency_per_year=0.0,
                income_for_food_percentage=0.0,
            ),
        ],
        national_pou_percent=55.0,
    )


def test_to_records_matches_output_schema():
    records = _result().to_records()
    assert records == [
        {
            "scenario": "ssp2",
            "quintile": 1,
            "pou_percent": 55.0,
            "penalized_diversity_per_year": 0.0,
            "penalized_sufficiency_per_year": 0.0,
            "income_for_food_percentage": 0.0,
        },
    ]
