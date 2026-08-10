"""Enumerations and constants for the Food Security module."""

from enum import Enum


class FoodGroup(str, Enum):
    """Coarse food groups every commodity maps to for the diversity rules.

    A balanced diet is not just enough calories but calories from a spread of
    groups. Each commodity is tagged with one of these, and the diet
    requirements bound how much of total energy each group may supply.
    """

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
