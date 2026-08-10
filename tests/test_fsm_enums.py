"""Tests for fsm enums."""

from food_security.fsm.enums import AllocationDirection, FoodGroup


def test_food_group_values():
    assert FoodGroup.CARBS.value == "carbs"
    assert {g.value for g in FoodGroup} == {"carbs", "protein", "fat", "fruitvege"}


def test_allocation_direction_values():
    assert AllocationDirection.RICHEST_FIRST.value == "richest_first"
    assert {d.value for d in AllocationDirection} == {
        "richest_first",
        "poorest_first",
    }
