import pandas as pd
import pyomo.environ as pyo

from typing import Union, Optional, Dict

from pathlib import Path
from pyomo.util.infeasible import log_infeasible_constraints
import logging

logger = logging.getLogger("pyomo.util.infeasible")
logger.setLevel(logging.INFO)


class FSOptimizer:
    def __init__(
        self,
        input_df: pd.DataFrame,
        income_df: pd.DataFrame,
        population: Union[int, float],
        MDER: float,
        minimum_kcal: Optional[Union[int, float]] = None,
        theta_dict: Optional[Dict[str, Union[int, float]]] = {
            "carb": 0.55,
            "protein": 0.10,
            "fat": 0.15,
            "fruitvege": 0.4,
        },
        lambda_E: Optional[Union[int, float]] = 1.0,
        lambda_g: Optional[Dict[str, Union[int, float]]] = {
            g: 1.0 for g in ["carb", "protein", "fat", "fruitvege"]
        },
    ):
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

        self.MDER = self.MDER * self.population_per_quintile
        self.minimum_kcal = self.minimum_kcal * self.population_per_quintile

        self.theta_dict = theta_dict
        self.theta_dict["fruitvege"] = (
            self.theta_dict["fruitvege"] * self.population_per_quintile
        )

        self.lambda_E = lambda_E
        self.lambda_g = lambda_g

        self.model = self._build_model()
        self.solver = pyo.SolverFactory("ipopt")

    def _build_model(self):
        foods = self.input_df.index
        model = pyo.ConcreteModel()

        model.foods = pyo.Set(initialize=foods)

        model.p = pyo.Param(
            model.foods, initialize=self.input_df["usd_per_kg"].to_dict()
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

        model.availability = pyo.Constraint(
            model.foods, rule=self._availability_constraint
        )
        model.total_spending = pyo.Expression(rule=self._total_spending)
        model.spending = pyo.Constraint(rule=self._income_constraint)
        model.total_energy = pyo.Expression(rule=self._total_energy)
        model.min_energy = pyo.Constraint(rule=self._minimum_energy)
        model.d_energy = pyo.Var(domain=pyo.NonNegativeReals)
        # model.energy_deficit = pyo.Constraint(rule=self._energy_deficit_rule)

        model.groups = pyo.Set(initialize=list(self.class_dict.keys()))

        model.group_energy = pyo.Expression(
            model.groups,
            rule=self._group_energy,
        )

        model.group_consumption = pyo.Expression(
            model.groups, rule=self._group_consumption
        )

        model.d_group = pyo.Var(model.groups, domain=pyo.NonNegativeReals)

        model.group_deficit = pyo.Constraint(
            model.groups, rule=self._group_deficit_rule
        )
        model.objective = pyo.Objective(
            rule=self._objective_rule,
            sense=pyo.minimize,
        )

        return model

    def solve(self):
        consumption_results = {}
        consumption_pp_results = {}
        optimization_results = {}
        for q in range(5, 0, -1):
            self._solve_quintile(q)
            (
                quintile_consumption,
                quintile_consumption_pp,
                quintile_optimization_info,
            ) = self._extract_results()

            self.input_df["quantity"] = self.input_df["quantity"] - quintile_consumption
            self.input_df["quantity"] = self.input_df["quantity"].clip(lower=0)
            for food, quantity in self.input_df["quantity"].items():
                self.model.A[food].set_value(quantity)

            consumption_results[q] = quintile_consumption
            consumption_pp_results[q] = quintile_consumption_pp
            optimization_results[q] = quintile_optimization_info

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
                "consumed_energy_pp",
            ]
            + fraction_indices
            + kg_indices,
        )
        optimization_df = optimization_df.where(optimization_df.abs() > 1e-4, 0)

        return consumption_df, consumption_pp_df, optimization_df

    def _solve_quintile(self, q):
        income_q = self.income_df[self.income_df["income_quintiles"] == q][
            "consumption_usd_pp_day"
        ].iloc[0]
        income_q = income_q * self.population_per_quintile
        self.model.income.set_value(income_q)
        self.solver.solve(self.model)
        # log_infeasible_constraints(
        #     self.model,
        #     logger=logger,
        #     log_expression=True,
        #     log_variables=True,
        # )

    def _extract_results(self):
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
        return m.C[c] <= m.A[c]

    def _total_spending(self, m):
        return sum(m.p[c] * m.C[c] for c in m.foods)

    def _income_constraint(self, m):
        return m.total_spending <= m.income

    def _total_energy(self, m):
        return sum(m.E[c] * m.C[c] for c in m.foods)

    def _minimum_energy(self, m):
        return m.total_energy >= self.minimum_kcal

    def _energy_deficit_rule(self, m):
        return m.d_energy >= (m.MDER - m.total_energy) / m.MDER

    def _group_energy(self, m, g):
        return sum(m.E[c] * m.C[c] for c in self.class_dict[g])

    def _group_consumption(self, m, g):
        return sum(m.C[c] for c in self.class_dict[g])

    def _group_deficit_rule(self, m, g):
        if g == "fruitvege":
            rule = m.d_group[g] >= self.theta_dict[g] - m.group_consumption[g]
        else:
            rule = (
                m.d_group[g] >= self.theta_dict[g] - m.group_energy[g] / m.total_energy
            )
        return rule

    def _objective_rule(self, m):

        food_cost = sum(m.p[c] * m.C[c] for c in m.foods)

        energy_penalty = self.lambda_E * m.d_energy

        diversity_penalty = sum(self.lambda_g[g] * m.d_group[g] for g in m.groups)

        return food_cost + energy_penalty + diversity_penalty
