"""Tests for fsm run configuration models."""

import pytest
from pydantic import ValidationError

from food_security.fsm.config import PenaltyWeights, RunConfig
from food_security.fsm.enums import AllocationDirection


def test_runconfig_defaults():
    cfg = RunConfig(weights=PenaltyWeights(lambda_energy=1.0, lambda_diversity=1.0))
    assert cfg.allocation_direction is AllocationDirection.RICHEST_FIRST
    assert cfg.solver_options == {}


def test_penalty_weights_reject_negative():
    with pytest.raises(ValidationError):
        PenaltyWeights(lambda_energy=-1.0, lambda_diversity=1.0)
