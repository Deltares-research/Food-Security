"""Optimization routines for food-security scenario analysis.

This module builds and solves a Pyomo-based optimization model that allocates
food consumption across nutrient groups while respecting spending, energy, and
availability constraints for each household income quintile.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Union

import numpy as np
import pandas as pd
import pyomo.environ as pyo
from pyomo.util.infeasible import log_infeasible_constraints

logger = logging.getLogger("pyomo.util.infeasible")
logger.setLevel(logging.INFO)


class FSOptimizer:
    """Solve a food-demand optimization problem from household input data.

    The optimizer balances total food spending against minimum energy needs and
    diversity targets for major food groups, iterating across income quintiles to
    estimate realistic consumption patterns.
    """

    def __init__(
        self,
        input_df: pd.DataFrame,
        income_df: pd.DataFrame,
        population: Union[int, float],
        MDER: float,
        minimum_kcal: Optional[Union[int, float]] = None,
        theta_min_dict: Optional[Dict[str, Union[int, float]]] = {
            "carb": 0.0,
            "protein": 0.24,
            "fat": 0.15,
            "fruitvege": 0.4,
        },
        theta_max_dict: Optional[Dict[str, Union[int, float]]] = {
            "carb": 0.7,
            "protein": 0.3,
            "fat": 0.2,
            "fruitvege": 0.5,
        },
        lambda_p: Optional[Union[int, float]] = 1.0,
        lambda_E: Optional[Union[int, float]] = 1.0,
        lambda_g: Optional[Dict[str, Union[int, float]]] = {
            g: 1.0 for g in ["carb", "protein", "fat", "fruitvege"]
        },
    ):
        """Initialize the food-security optimization model.

        Args:
            input_df: Crop-level input table containing food names, food class,
                prices, calories, and available quantities.
            income_df: Household income profile by income quintile, including
                consumption and spending assumptions.
            population: Total population covered by the model; this is split into
                five equal quintile groups for the optimization.
            MDER: Minimum dietary energy requirement used as the baseline energy
                constraint for the population segment.
            minimum_kcal: Optional override for the minimum energy threshold. If
                not provided, it defaults to ``MDER``.
            theta_min_dict: Minimum allowed share of total energy or food-group
                intake for each category, e.g. carbohydrates, protein, fat, and
                fruit/vegetables.
            theta_max_dict: Maximum allowed share of total energy or food-group
                intake for each category.
            lambda_p: Weighting coefficient for the spending penalty in the
                objective function.
            lambda_E: Weighting coefficient for the energy-deficit penalty in the
                objective function.
            lambda_g: Per-group penalty weights used to penalize imbalances in
                food-group diversity.
        """
        self.input_df = input_df
        self.class_dict = (
            self.input_df.groupby("class")["crop_name_fao"]
            .unique()
            .apply(list)
            .to_dict()
        )

        if "-" in self.class_dict:
            del self.class_dict["-"]
        self.input_df = self.input_df.set_index("crop_name_fao")
        self.income_df = income_df
        self.population_per_quintile = int(population / 5)
        self.MDER = MDER
        self.minimum_kcal = minimum_kcal
        if self.minimum_kcal is None:
            self.minimum_kcal = MDER

        # Convert from required energy per person to required energy per quintile
        self.MDER = self.MDER * self.population_per_quintile
        self.minimum_kcal = self.minimum_kcal * self.population_per_quintile

        self.theta_min_dict = theta_min_dict
        self.theta_max_dict = theta_max_dict
        # Convert kg per person to kg per quintile
        self.theta_min_dict["fruitvege"] = (
            self.theta_min_dict["fruitvege"] * self.population_per_quintile
        )
        self.theta_max_dict["fruitvege"] = (
            self.theta_max_dict["fruitvege"] * self.population_per_quintile
        )
        # Penalty weights
        self.lambda_p = lambda_p
        self.lambda_E = lambda_E
        self.lambda_g = lambda_g
        # Create optimization model to solve.
        self.model = self._build_model()
        self.solver = pyo.SolverFactory("ipopt")

    def _build_model(self):
        """Create the Pyomo optimization model and all associated constraints.

        Returns:
            pyo.ConcreteModel: The assembled optimization model for the current
            food-demand problem.
        """
        foods = self.input_df.index
        model = pyo.ConcreteModel()

        model.foods = pyo.Set(initialize=foods)

        model.p = pyo.Param(
            model.foods, initialize=self.input_df["market_price"].to_dict()
        )
        model.E = pyo.Param(
            model.foods, initialize=self.input_df["calories_kcal_kg"].to_dict()
        )
        model.A = pyo.Param(
            model.foods, initialize=self.input_df["quantity"].to_dict(), mutable=True
        )
        model.MDER = pyo.Param(initialize=self.MDER)

        model.C = pyo.Var(model.foods, domain=pyo.NonNegativeReals, initialize=1.0)
        model.income = pyo.Param(mutable=True)
        model.income_p_spending = pyo.Param(mutable=True)

        model.availability = pyo.Constraint(
            model.foods, rule=self._availability_constraint
        )
        # Food expenditure cannot exceed income
        model.total_spending = pyo.Expression(rule=self._total_spending)
        model.spending = pyo.Constraint(rule=self._income_constraint)
        # d_p from the paper. The maxiumum is represented by food expenditure rule.
        model.d_spending = pyo.Var(domain=pyo.NonNegativeReals)
        model.food_expenditure = pyo.Constraint(rule=self._food_expenditure_rule)

        # Total consumed energy must exceed or equal minimum required energy.
        model.total_energy = pyo.Expression(rule=self._total_energy)
        model.min_energy = pyo.Constraint(rule=self._minimum_energy)

        # d_E from the paper. The maxiumum is represented by energy deficit rule
        model.d_energy = pyo.Var(domain=pyo.NonNegativeReals)
        model.energy_deficit = pyo.Constraint(rule=self._energy_deficit_rule)

        model.groups = pyo.Set(initialize=list(self.class_dict.keys()))
        # Total consumption per group in kcal
        model.group_energy = pyo.Expression(
            model.groups,
            rule=self._group_energy,
        )
        # Total consumption per group in kg
        model.group_consumption = pyo.Expression(
            model.groups, rule=self._group_consumption
        )
        # d_g from the paper. The maxiumum is represented by group deficit rule and group excess rule.
        model.d_group = pyo.Var(model.groups, domain=pyo.NonNegativeReals)

        model.group_deficit = pyo.Constraint(
            model.groups, rule=self._group_deficit_rule
        )
        model.group_excess = pyo.Constraint(model.groups, rule=self._group_excess_rule)
        # Define objectibe function.
        model.objective = pyo.Objective(
            rule=self._objective_rule,
            sense=pyo.minimize,
        )

        return model

    def solve(self):
        """Solve the optimization sequentially for each income quintile.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: Consumption totals,
            per-person consumption, and summary optimization metrics for each
            quintile.
        """
        consumption_results = {}
        consumption_pp_results = {}
        optimization_results = {}
        for q in range(5, 0, -1):
            # Solve for the quintile.
            self._solve_quintile(q)
            (
                quintile_consumption,
                quintile_consumption_pp,
                quintile_optimization_info,
            ) = self._extract_results()
            # Remove consumed crops from availability and update availability in the model.
            self.input_df["quantity"] = self.input_df["quantity"] - quintile_consumption
            self.input_df["quantity"] = self.input_df["quantity"].clip(lower=0)
            for food, quantity in self.input_df["quantity"].items():
                self.model.A[food].set_value(quantity)
            # Store quintile results.
            consumption_results[q] = quintile_consumption
            consumption_pp_results[q] = quintile_consumption_pp
            optimization_results[q] = quintile_optimization_info
        # Combine quintile results into one DataFrame per output.
        consumption_df = pd.DataFrame(consumption_results, index=self.model.foods)
        consumption_df = consumption_df.where(consumption_df.abs() > 1e-4, 0)
        consumption_pp_df = pd.DataFrame(consumption_pp_results, index=self.model.foods)
        consumption_pp_df = consumption_pp_df.where(consumption_pp_df.abs() > 1e-4, 0)
        fraction_indices = [f"{g}_fraction" for g in self.model.groups]
        kg_indices = [f"{g}_kg" for g in self.model.groups]
        optimization_df = pd.DataFrame(
            optimization_results,
            index=[
                "objective function",
                "spending_pp",
                "percentage_spending",
                "consumed_energy_pp",
            ]
            + fraction_indices
            + kg_indices,
        )
        optimization_df = optimization_df.where(optimization_df.abs() > 1e-4, 0)

        return consumption_df, consumption_pp_df, optimization_df

    def _solve_quintile(self, q):
        """Solve the optimization model for a single income quintile.

        Args:
            q: Income quintile index from 1 to 5 to be evaluated.
        """
        # Update income in the optimization model.
        income_q = self.income_df[self.income_df["income_quintiles"] == q][
            "consumption_usd_pp_day"
        ].iloc[0]
        income_q = income_q * self.population_per_quintile
        self.model.income.set_value(income_q)
        # Update share of income spent on food in the optimization model.
        income_p_spending_q = self.income_df[self.income_df["income_quintiles"] == q][
            "p_spent_food_max"
        ].iloc[0]
        self.model.income_p_spending.set_value(income_p_spending_q)
        # Solve the model.
        self.solver.solve(self.model)
        # log_infeasible_constraints(
        #     self.model,
        #     logger=logger,
        #     log_expression=True,
        #     log_variables=True,
        # )

    def _extract_results(self):
        """Extract optimization outputs from the current model solution.

        Returns:
            tuple[list, list, list]: Food consumption values, per-person
            consumption values, and objective summary metrics.
        """
        consumptions = []
        consumptions_pp = []
        optimization_info = []
        for c in self.model.foods:
            consumptions.append(pyo.value(self.model.C[c]))
            consumptions_pp.append(
                pyo.value(self.model.C[c]) / self.population_per_quintile
            )

        optimization_info.append(pyo.value(self.model.objective))
        optimization_info.append(
            pyo.value(self.model.total_spending) / self.population_per_quintile
        )
        optimization_info.append(
            pyo.value(self.model.total_spending) / pyo.value(self.model.income)
        )
        optimization_info.append(
            pyo.value(self.model.total_energy) / self.population_per_quintile
        )
        for g in self.model.groups:
            optimization_info.append(
                pyo.value(self.model.group_energy[g])
                / pyo.value(self.model.total_energy)
            )
        for g in self.model.groups:
            optimization_info.append(
                pyo.value(self.model.group_consumption[g])
                / self.population_per_quintile
            )

        return consumptions, consumptions_pp, optimization_info

    def _availability_constraint(self, m, c):
        """Limit food consumption to the available quantity for each food item."""
        return m.C[c] <= m.A[c]

    def _total_spending(self, m):
        """Compute the monetary cost of the chosen food consumption bundle."""
        return sum(m.p[c] * m.C[c] for c in m.foods)

    def _income_constraint(self, m):
        """Enforce that total spending does not exceed household income."""
        return m.total_spending <= m.income

    def _total_energy(self, m):
        """Calculate the total energy supplied by the modeled food combination."""
        return sum(m.E[c] * m.C[c] for c in m.foods)

    def _minimum_energy(self, m):
        """Ensure that energy consumption meets the minimum dietary requirement."""
        return m.total_energy >= self.minimum_kcal

    def _energy_deficit_rule(self, m):
        """Track the relative shortfall between minimum energy need and achieved energy."""
        return m.d_energy >= (m.MDER - m.total_energy) / m.MDER

    def _group_energy(self, m, g):
        """Sum the energy contribution from foods in a given food class."""
        return sum(m.E[c] * m.C[c] for c in self.class_dict[g])

    def _group_consumption(self, m, g):
        """Total quantity consumed across foods in a specific food group."""
        return sum(m.C[c] for c in self.class_dict[g])

    def _group_deficit_rule(self, m, g):
        """Penalize under-consumption relative to minimum group share targets.
        Split for micro nutrients and macro nutrients
        """
        if g == "fruitvege":
            rule = (
                m.d_group[g]
                >= (self.theta_min_dict[g] - m.group_consumption[g])
                / self.theta_min_dict[g]
            )
        else:
            rule = (
                m.d_group[g]
                >= self.theta_min_dict[g] - m.group_energy[g] / m.total_energy
            )
        return rule

    def _group_excess_rule(self, m, g):
        """Penalize over-consumption above the allowed maximum group share. Only applicable for macro nutrients."""
        if g != "fruitvege":
            rule = (
                m.d_group[g]
                >= m.group_energy[g] / m.total_energy - self.theta_max_dict[g]
            )
            return rule
        elif g == "fruitvege":
            rule = m.d_group[g] >= m.group_consumption[g] / self.theta_max_dict[g] - 1
            return rule
        return pyo.Constraint.Skip

    def _food_expenditure_rule(self, m):
        """Capture the gap between spending and the targeted food-share threshold."""
        return m.d_spending >= m.total_spending / m.income - m.income_p_spending

    def _objective_rule(self, m):
        """Minimize spending, energy shortfall, and group-balance penalties."""

        food_cost = sum(m.p[c] * m.C[c] for c in m.foods)
        spending_penalty = self.lambda_p * m.d_spending

        energy_penalty = self.lambda_E * m.d_energy

        diversity_penalty = sum(self.lambda_g[g] * m.d_group[g] for g in m.groups)

        return spending_penalty + energy_penalty + diversity_penalty
