"""Trust score (§9) — app/services/trust.py."""

import pytest

from app.services import trust


def test_apply_trust_penalty_clamps_to_zero():
    assert trust.apply_trust_penalty(10, 50) == 0


def test_apply_trust_penalty_normal_case():
    assert trust.apply_trust_penalty(100, 15) == 85


def test_apply_trust_bonus_clamps_to_hundred():
    assert trust.apply_trust_bonus(95, 20) == 100


@pytest.mark.parametrize(
    "previous,new,expected",
    [
        (None, 100, True),  # первый замер сезона — всегда правдоподобен
        (0, 5, True),
        (10, 12, True),  # +20%
        (10, 20, False),  # +100%
        (10, 7.6, True),  # -24%
        (10, 7.0, False),  # -30%
    ],
)
def test_is_measurement_plausible(previous, new, expected):
    assert trust.is_measurement_plausible(previous, new) is expected


def test_meets_squad_trust_threshold():
    assert trust.meets_squad_trust_threshold(40) is True
    assert trust.meets_squad_trust_threshold(39) is False
    assert trust.meets_squad_trust_threshold(100) is True
