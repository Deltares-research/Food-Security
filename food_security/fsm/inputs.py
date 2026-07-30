"""Typed input models for the Food Security module (no file I/O)."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field, model_validator

from food_security.fsm.enums import FoodGroup

_SHARE_SUM_TOLERANCE = 1e-6


class ShareBounds(BaseModel):
    """Minimum (and optional maximum) share of total calories for a food group."""

    min: float = Field(ge=0, le=1)
    max: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if self.max is not None and self.min > self.max:
            msg = "ShareBounds.min cannot exceed ShareBounds.max"
            raise ValueError(msg)
        return self


class DietRequirements(BaseModel):
    """Dietary-diversity requirements: per-group calorie-share bounds (theta_g)."""

    group_bounds: dict[FoodGroup, ShareBounds]
    fruitvege_grams_per_capita_day: float | None = Field(default=None, ge=0)


class Commodity(BaseModel):
    """Static reference data for one food commodity."""

    code: str
    name: str
    fao_name: str | None = None
    food_group: FoodGroup | None = None  # None => non-food (excluded from the diet)
    energy_kcal_per_kg: float = Field(ge=0)


class Quintile(BaseModel):
    """One income quintile's economic and demographic parameters."""

    index: int = Field(ge=1, le=5)
    food_budget_per_capita_day: float = Field(ge=0)
    population_share: float = Field(gt=0, le=1)
    cv: float = Field(gt=0)
    mder: float = Field(gt=0)


class SupplyComponents(BaseModel):
    """Optional helper to derive net availability from its four components."""

    production_delta: float = Field(default=0.0, ge=0)
    production_other: float = Field(default=0.0, ge=0)
    imports: float = Field(default=0.0, ge=0)
    exports: float = Field(default=0.0, ge=0)

    def net(self) -> float:
        """Return net available quantity, clamped at zero."""
        total = self.production_delta + self.production_other + self.imports - self.exports
        return max(0.0, total)


class ModelInputs(BaseModel):
    """All inputs for a single (country, scenario, year) run."""

    country: str
    scenario: str
    year: int
    commodities: list[Commodity]
    availability: dict[str, float]  # net tonnes per commodity code
    prices: dict[str, float]  # currency per tonne per commodity code
    quintiles: list[Quintile]
    diet: DietRequirements

    @model_validator(mode="after")
    def _check(self) -> Self:
        codes = [c.code for c in self.commodities]
        if len(codes) != len(set(codes)):
            msg = "commodity codes must be unique"
            raise ValueError(msg)
        code_set = set(codes)

        for key, value in self.availability.items():
            if key not in code_set:
                msg = f"availability key {key!r} is not a known commodity code"
                raise ValueError(msg)
            if value < 0:
                msg = f"availability for {key!r} must be non-negative"
                raise ValueError(msg)

        for key, value in self.prices.items():
            if key not in code_set:
                msg = f"prices key {key!r} is not a known commodity code"
                raise ValueError(msg)
            if value < 0:
                msg = f"price for {key!r} must be non-negative"
                raise ValueError(msg)

        indices = [q.index for q in self.quintiles]
        if len(indices) != len(set(indices)):
            msg = "quintile indices must be unique"
            raise ValueError(msg)

        total_share = sum(q.population_share for q in self.quintiles)
        if abs(total_share - 1.0) > _SHARE_SUM_TOLERANCE:
            msg = f"quintile population_share must sum to 1.0 (got {total_share})"
            raise ValueError(msg)

        return self
