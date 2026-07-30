"""Tests for fsm enums."""

from food_security.fsm.enums import ALLOCATION_ORDER, FoodGroup


def test_food_group_values():
    assert FoodGroup.CARBS.value == "carbs"
    assert {g.value for g in FoodGroup} == {"carbs", "protein", "fat", "fruitvege"}


def test_allocation_order_is_high_to_low():
    assert ALLOCATION_ORDER == (5, 4, 3, 2, 1)
