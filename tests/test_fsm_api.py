"""End-to-end smoke test through the public fsm API."""

from food_security import fsm


def test_end_to_end_through_public_api():
    inputs = fsm.ModelInputs(
        country="Egypt",
        scenario="ssp2",
        year=2020,
        commodities=[
            fsm.Commodity(
                code="RICE",
                name="Rice",
                food_group=fsm.FoodGroup.CARBS,
                energy_kcal_per_kg=1300.0,
            ),
        ],
        availability={"RICE": 1000.0},
        prices={"RICE": 250.0},
        quintiles=[
            fsm.Quintile(
                index=i,
                food_budget_per_capita_day=20.0,
                population_share=0.2,
                cv=0.3,
                mder=1806.61,
            )
            for i in range(1, 6)
        ],
        diet=fsm.DietRequirements(
            group_bounds={fsm.FoodGroup.CARBS: fsm.ShareBounds(min=0.55, max=0.75)},
        ),
    )
    config = fsm.RunConfig(
        weights=fsm.PenaltyWeights(lambda_energy=1.0, lambda_diversity=1.0),
    )

    result = fsm.FoodSecurityModel(inputs, config).run()

    assert isinstance(result, fsm.FoodSecurityResult)
    assert len(result.to_records()) == 5
