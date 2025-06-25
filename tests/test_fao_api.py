import pytest

from food_security.fao_api import get_food_production_df


def test_get_food_production_df():
    df = get_food_production_df(country_name="Viet Nam", year=2020)
    assert not df.empty
    assert df.Year.unique() == "2020"
    assert df.Area.unique() == "Viet Nam"

    with pytest.raises(ValueError, match="No FAO data found for the given parameters."):
        get_food_production_df(country_name="Viet Nam", year=2026)
