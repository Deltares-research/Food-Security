"""Typed output models for the Food Security module."""

from __future__ import annotations

from pydantic import BaseModel


class QuintileOutcome(BaseModel):
    """Food-security outcome for one income quintile.

    Field names mirror the reference workbook's `output` sheet (plus `dec`).
    """

    quintile: int
    dec: float
    pou_percent: float
    penalized_diversity_per_year: float
    penalized_sufficiency_per_year: float
    income_for_food_percentage: float


class FoodSecurityResult(BaseModel):
    """Result of a single (country, scenario, year) run."""

    country: str
    scenario: str
    year: int
    per_quintile: list[QuintileOutcome]
    national_pou_percent: float

    def to_records(self) -> list[dict]:
        """Flatten per-quintile outcomes to the reference `output` sheet shape."""
        return [
            {
                "scenario": self.scenario,
                "quintile": o.quintile,
                "pou_percent": o.pou_percent,
                "penalized_diversity_per_year": o.penalized_diversity_per_year,
                "penalized_sufficiency_per_year": o.penalized_sufficiency_per_year,
                "income_for_food_percentage": o.income_for_food_percentage,
            }
            for o in self.per_quintile
        ]
