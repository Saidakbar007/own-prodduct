"""Округление по существу (§8 NEWLIFE_V8_SPEC.md) — таблицы случаев."""

import pytest

from app.newlife import rounding


@pytest.mark.parametrize(
    "kg,expected",
    [(41.0, 40.0), (42.5, 42.5), (43.6, 42.5), (44.0, 45.0)],
)
def test_round_barbell(kg, expected):
    assert rounding.round_barbell(kg) == expected


@pytest.mark.parametrize(
    "kg,expected",
    [(4.4, 4.0), (4.6, 5.0), (10.0, 10.0), (11.0, 12.0), (12.9, 12.0)],
)
def test_round_dumbbell_step_changes_above_10kg(kg, expected):
    assert rounding.round_dumbbell(kg) == expected


def test_round_reps_is_integer():
    assert rounding.round_reps(7.4) == 7
    assert rounding.round_reps(7.6) == 8
    assert isinstance(rounding.round_reps(7.4), int)


@pytest.mark.parametrize(
    "kg,expected",
    [(80.04, 80.0), (80.06, 80.1), (80.15, 80.2)],
)
def test_round_bodyweight_one_decimal(kg, expected):
    assert rounding.round_bodyweight(kg) == pytest.approx(expected)


@pytest.mark.parametrize(
    "cm,expected",
    [(80.2, 80.0), (80.3, 80.5), (80.74, 80.5), (80.76, 81.0)],
)
def test_round_circumference_half_cm(cm, expected):
    assert rounding.round_circumference(cm) == pytest.approx(expected)


def test_round_run_time_to_30_seconds():
    assert rounding.round_run_time_seconds(616) == 630  # чуть больше 10:15 -> 10:30
    assert rounding.round_run_time_seconds(600) == 600
    assert rounding.round_run_time_seconds(614) == 600


def test_round_steps_to_500():
    assert rounding.round_steps(8240) == 8000
    assert rounding.round_steps(8260) == 8500


def test_round_sleep_to_15_minutes():
    assert rounding.round_sleep_minutes(427) == 420  # 7h07 -> 7h00
    assert rounding.round_sleep_minutes(428) == 435  # 7h08 -> 7h15


def test_round_money_to_1000_sum():
    assert rounding.round_money(125499) == 125000
    assert rounding.round_money(125600) == 126000


@pytest.mark.parametrize("p,expected", [(42.4, 42), (42.6, 43)])
def test_round_percent(p, expected):
    assert rounding.round_percent(p) == expected


@pytest.mark.parametrize(
    "days,expected",
    [(5, ("days", 5)), (21, ("days", 21)), (22, ("weeks", 3)), (63, ("weeks", 9))],
)
def test_forecast_unit_and_value(days, expected):
    assert rounding.forecast_unit_and_value(days) == expected


def test_forecast_never_negative_days():
    assert rounding.forecast_unit_and_value(-3) == ("days", 0)


def test_rolling_average_uses_last_window_values():
    values = [1, 2, 3, 4, 5, 6, 7, 100]  # последние 7: 2..7,100
    avg = rounding.rolling_average(values, window=7)
    assert avg == pytest.approx(sum([2, 3, 4, 5, 6, 7, 100]) / 7)


def test_rolling_average_empty_is_none():
    assert rounding.rolling_average([]) is None
