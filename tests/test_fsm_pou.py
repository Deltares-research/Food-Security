"""Tests for the pure PoU math."""

import math
from statistics import NormalDist

import pytest

from food_security.fsm.pou import national_pou, pou_from_dec


def test_pou_when_dec_equals_mder_is_phi_of_half_sigma():
    # When dec == mder, PoU = Phi(sigma/2), sigma = sqrt(ln(1 + cv^2)).
    dec = mder = 2000.0
    cv = 0.3
    sigma = math.sqrt(math.log(1 + cv**2))
    expected = NormalDist().cdf(sigma / 2)
    assert pou_from_dec(dec, cv, mder) == pytest.approx(expected, abs=1e-9)
    assert pou_from_dec(dec, cv, mder) == pytest.approx(0.5583, abs=1e-3)


def test_pou_higher_when_dec_below_mder():
    high = pou_from_dec(dec=1500.0, cv=0.3, mder=1806.61)
    low = pou_from_dec(dec=2500.0, cv=0.3, mder=1806.61)
    assert high > low
    assert 0.0 <= low <= 1.0
    assert 0.0 <= high <= 1.0


def test_pou_from_dec_rejects_nonpositive():
    with pytest.raises(ValueError, match="dec"):
        pou_from_dec(dec=0.0, cv=0.3, mder=1800.0)


def test_national_pou_is_population_weighted_mean():
    pou = {1: 0.5, 2: 0.4, 3: 0.3, 4: 0.2, 5: 0.1}
    share = {1: 0.2, 2: 0.2, 3: 0.2, 4: 0.2, 5: 0.2}
    assert national_pou(pou, share) == pytest.approx(0.3)


def test_national_pou_respects_unequal_shares():
    pou = {1: 1.0, 2: 0.0}
    share = {1: 0.75, 2: 0.25}
    assert national_pou(pou, share) == pytest.approx(0.75)
