"""Tests for fsm run configuration models."""

import pytest
from pydantic import ValidationError

from food_security.fsm.config import PenaltyWeights, RunConfig


def test_runconfig_defaults():
    cfg = RunConfig(weights=PenaltyWeights(lambda_energy=1.0, lambda_diversity=1.0))
    assert cfg.allocation_order == (5, 4, 3, 2, 1)
    assert cfg.solver_options == {}


def test_penalty_weights_reject_negative():
    with pytest.raises(ValidationError):
        PenaltyWeights(lambda_energy=-1.0, lambda_diversity=1.0)
