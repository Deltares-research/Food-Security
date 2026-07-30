"""Tests for fsm error hierarchy."""

from food_security.fsm.errors import (
    FSMError,
    InfeasibleAllocation,
    MissingCommodityData,
)


def test_error_hierarchy():
    assert issubclass(InfeasibleAllocation, FSMError)
    assert issubclass(MissingCommodityData, FSMError)
    assert issubclass(FSMError, Exception)
