"""Enumerations and constants for the Food Security module."""

from enum import Enum


class FoodGroup(str, Enum):
    """Diet food groups used for the dietary-diversity constraints."""

    CARBS = "carbs"
    PROTEIN = "protein"
    FAT = "fat"
    FRUITVEGE = "fruitvege"


# Income quintiles in allocation order: richest (Q5) is served first, poorest (Q1) last.
ALLOCATION_ORDER: tuple[int, ...] = (5, 4, 3, 2, 1)
