"""Pure Prevalence-of-Undernourishment (PoU) math (FAO log-normal method).

PoU is the share of a population whose habitual energy intake falls below its
Minimum Dietary Energy Requirement (MDER). Following the FAO method, habitual
intake is treated as a log-normal distribution whose mean is the group's
Dietary Energy Consumption (DEC) and whose spread is set by a coefficient of
variation (CV); PoU is the probability mass of that distribution below MDER.

These functions are deliberately free of the model's types so the math can be
tested and reused in isolation.
"""

from __future__ import annotations

import math
from statistics import NormalDist

_POP_SHARE_TOLERANCE = 1e-12


def pou_from_dec(dec: float, cv: float, mder: float) -> float:
    """Return the PoU fraction for a group given its mean intake, CV, and requirement.

    Habitual intake is modelled as log-normal with mean `dec` and coefficient of
    variation `cv`; PoU is the probability that intake falls below `mder`.
    """
    if dec <= 0:
        msg = "dec must be positive"
        raise ValueError(msg)
    if cv <= 0:
        msg = "cv must be positive"
        raise ValueError(msg)
    if mder <= 0:
        msg = "mder must be positive"
        raise ValueError(msg)
    sigma = math.sqrt(math.log(1 + cv**2))
    mu = math.log(dec) - sigma**2 / 2
    return NormalDist().cdf((math.log(mder) - mu) / sigma)


def national_pou(
    pou_by_quintile: dict[int, float],
    population_share: dict[int, float],
) -> float:
    """Aggregate per-quintile PoU into a national figure (population-weighted mean).

    This deliberately replaces the paper's `PoU = sum_q PoU_q`, which can exceed
    100%.
    """
    total = sum(population_share.values())
    if abs(total) < _POP_SHARE_TOLERANCE:
        msg = "population shares sum to zero"
        raise ValueError(msg)
    weighted = sum(
        pou_by_quintile[q] * population_share[q] for q in pou_by_quintile
    )
    return weighted / total
