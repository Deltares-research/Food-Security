"""Typed input models for the Food Security module (no file I/O)."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field, model_validator

from food_security.fsm.enums import FoodGroup  # noqa: TC001 - pydantic runtime need

_SHARE_SUM_TOLERANCE = 1e-6


class ShareBounds(BaseModel):
    """Allowed share of total dietary energy that one food group may supply.

    Bounds are fractions of total calories (0-1). They encode the diversity
    rules, e.g. "carbohydrates supply between 45% and 65% of energy".
    """

    min: float = Field(
        ge=0,
        le=1,
        description="Minimum fraction of total calories from this group.",
    )
    max: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Maximum fraction of total calories, or None for no cap.",
    )

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if self.max is not None and self.min > self.max:
            msg = "ShareBounds.min cannot exceed ShareBounds.max"
            raise ValueError(msg)
        return self


class DietRequirements(BaseModel):
    """Dietary-diversity requirements the optimized diet is scored against.

    In the paper these are the theta_g parameters: for each food group, the
    share of total energy that group is allowed to supply.
    """

    group_bounds: dict[FoodGroup, ShareBounds] = Field(
        description="Per-food-group calorie-share bounds (the theta_g targets).",
    )
    fruitvege_grams_per_capita_day: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Optional absolute floor on fruit & vegetable intake "
            "(grams per capita per day), separate from the calorie-share bounds."
        ),
    )


class Commodity(BaseModel):
    """Static reference data for one food commodity (a row in the food list).

    Identifies the item and carries the one physical constant the model needs:
    its energy density, used to convert quantities (kg) into calories.
    """

    code: str = Field(description="Stable commodity key (e.g. the FAO item code).")
    name: str = Field(description="Human-readable commodity name.")
    fao_name: str | None = Field(
        default=None,
        description="Matching FAOSTAT item name, if different from `name`.",
    )
    food_group: FoodGroup | None = Field(
        default=None,
        description="Diet group this item counts toward; None means non-food.",
    )
    energy_kcal_per_kg: float = Field(
        ge=0,
        description="Energy density used to convert kg of this item into calories.",
    )


class Quintile(BaseModel):
    """One income quintile: a fifth of the population, ranked by income.

    Index 1 is the poorest fifth, 5 the richest. Carries the economics the
    allocation needs (how much this group can spend on food) and the two
    parameters the undernourishment calculation needs (`cv`, `mder`).
    """

    index: int = Field(
        ge=1,
        le=5,
        description="Quintile rank: 1 = poorest fifth, 5 = richest fifth.",
    )
    food_budget_per_capita_day: float = Field(
        ge=0,
        description="Money available to spend on food, per person per day.",
    )
    population_share: float = Field(
        gt=0,
        le=1,
        description="Fraction of the national population in this quintile (~0.2).",
    )
    cv: float = Field(
        gt=0,
        description=(
            "Coefficient of variation of habitual energy intake within the "
            "group: how unequally calories are spread across its members. "
            "Drives the width of the intake distribution in the PoU calc."
        ),
    )
    mder: float = Field(
        gt=0,
        description=(
            "Minimum Dietary Energy Requirement (kcal/capita/day): the intake "
            "threshold below which a person counts as undernourished."
        ),
    )


class SupplyComponents(BaseModel):
    """Optional helper to build one commodity's net availability from its parts.

    Net availability is what is actually on the domestic market for people to
    eat: everything produced or imported, minus what is exported. Callers can
    populate `availability` directly instead of using this helper.
    """

    production_delta: float = Field(
        default=0.0,
        ge=0,
        description="Production inside the delta (the modelled region).",
    )
    production_other: float = Field(
        default=0.0,
        ge=0,
        description="Production in the rest of the country, outside the delta.",
    )
    imports: float = Field(default=0.0, ge=0, description="Quantity imported.")
    exports: float = Field(default=0.0, ge=0, description="Quantity exported.")

    def net(self) -> float:
        """Return net available quantity (production + imports - exports), >= 0."""
        total = (
            self.production_delta
            + self.production_other
            + self.imports
            - self.exports
        )
        return max(0.0, total)


class ModelInputs(BaseModel):
    """All data for a single model run: one country, scenario, and year.

    Bundles the food list, how much of each food is available, what each food
    costs, the population split into income quintiles, and the diet rules. The
    validators enforce the cross-field invariants the rest of the pipeline
    assumes (unique/known commodity codes, non-negative amounts, and quintiles
    that cover 1..5 with population shares summing to 1).
    """

    country: str = Field(description="Country or delta the run applies to.")
    scenario: str = Field(description="Scenario label (e.g. a climate/policy case).")
    year: int = Field(description="Calendar year the inputs describe.")
    commodities: list[Commodity] = Field(
        description="The food list; every code used below must appear here.",
    )
    availability: dict[str, float] = Field(
        description="Net available quantity (tonnes) keyed by commodity code.",
    )
    prices: dict[str, float] = Field(
        description="Producer/market price (currency per tonne) by commodity code.",
    )
    quintiles: list[Quintile] = Field(
        description="The five income quintiles; must cover indices 1..5 exactly.",
    )
    diet: DietRequirements = Field(
        description="Diversity bounds the optimized diet is scored against.",
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        code_set = self._check_commodities()
        self._check_amounts(self.availability, "availability")
        self._check_amounts(self.prices, "price")
        self._check_keys_known(self.availability, code_set, "availability")
        self._check_keys_known(self.prices, code_set, "prices")
        self._check_quintiles()
        return self

    def _check_commodities(self) -> set[str]:
        codes = [c.code for c in self.commodities]
        if len(codes) != len(set(codes)):
            msg = "commodity codes must be unique"
            raise ValueError(msg)
        return set(codes)

    @staticmethod
    def _check_keys_known(
        amounts: dict[str, float], code_set: set[str], label: str,
    ) -> None:
        for key in amounts:
            if key not in code_set:
                msg = f"{label} key {key!r} is not a known commodity code"
                raise ValueError(msg)

    @staticmethod
    def _check_amounts(amounts: dict[str, float], label: str) -> None:
        for key, value in amounts.items():
            if value < 0:
                msg = f"{label} for {key!r} must be non-negative"
                raise ValueError(msg)

    def _check_quintiles(self) -> None:
        indices = [q.index for q in self.quintiles]
        if len(indices) != len(set(indices)):
            msg = "quintile indices must be unique"
            raise ValueError(msg)

        if set(indices) != {1, 2, 3, 4, 5}:
            msg = "quintiles must cover indices 1..5 exactly"
            raise ValueError(msg)

        total_share = sum(q.population_share for q in self.quintiles)
        if abs(total_share - 1.0) > _SHARE_SUM_TOLERANCE:
            msg = f"quintile population_share must sum to 1.0 (got {total_share})"
            raise ValueError(msg)
