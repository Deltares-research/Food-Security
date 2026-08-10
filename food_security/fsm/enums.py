"""Enumerations and constants for the Food Security module."""

from enum import Enum


class FoodGroup(str, Enum):
    """Diet food groups used for the dietary-diversity constraints."""

    CARBS = "carbs"
    PROTEIN = "protein"
    FAT = "fat"
    FRUITVEGE = "fruitvege"


class AllocationDirection(str, Enum):
    """Order in which income groups are served by the allocation cascade.

    The concrete sequence is derived at runtime by sorting the quintiles on
    their index, so this stays correct regardless of how many groups exist.
    The paper's cascade serves the richest first (they buy their optimal diet)
    and leaves the poorest the residual.
    """

    RICHEST_FIRST = "richest_first"
    POOREST_FIRST = "poorest_first"
