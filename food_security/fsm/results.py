"""Typed output models for the Food Security module."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QuintileOutcome(BaseModel):
    """Food-security outcome for one income quintile.

    This is the reported form of the allocation: percentages are already
    scaled to 0-100. Field names mirror the reference workbook's `output`
    sheet (plus `dec`) so results line up column-for-column.
    """

    quintile: int = Field(description="Quintile index: 1 = poorest, 5 = richest.")
    dec: float = Field(
        description="Achieved mean energy intake (kcal/capita/day).",
    )
    pou_percent: float = Field(
        description=(
            "Prevalence of Undernourishment: percent of the quintile whose "
            "habitual intake falls below MDER."
        ),
    )
    penalized_diversity_per_year: float = Field(
        description="Diversity-violation penalty, expressed per year.",
    )
    penalized_sufficiency_per_year: float = Field(
        description="Energy-shortfall penalty, expressed per year.",
    )
    income_for_food_percentage: float = Field(
        description="Percent of income the quintile spends to afford its diet.",
    )


class FoodSecurityResult(BaseModel):
    """Result of a single model run: one country, scenario, and year.

    Bundles the per-quintile outcomes with the population-weighted national
    undernourishment figure.
    """

    country: str = Field(description="Country or delta the result applies to.")
    scenario: str = Field(description="Scenario label carried through from inputs.")
    year: int = Field(description="Calendar year the result describes.")
    per_quintile: list[QuintileOutcome] = Field(
        description="One outcome per income quintile.",
    )
    national_pou_percent: float = Field(
        description=(
            "Population-weighted mean of the per-quintile PoU, as a percent."
        ),
    )

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
