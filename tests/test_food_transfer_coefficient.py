import numpy as np

from food_security.food_transfer_coefficient import FoodTransferCoefficient


def test_calculate_road_density(regions):
    # Only select one geometry to reduce processing time for testing
    region = regions.iloc[[0]]
    ftc = FoodTransferCoefficient(cfg={}, region=region)
    ftc.calculate_road_density()
    assert "road_density" in ftc.region.columns
    assert np.isclose(ftc.region.iloc[0]["road_density"], 1.834, rtol=0.001)
