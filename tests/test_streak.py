"""Юнит-тесты подсчёта streak (без БД — чистая функция)."""

from datetime import date, timedelta

from app.services.streak import calculate_streak


def test_empty_history_gives_zero_streak():
    assert calculate_streak(set()) == 0


def test_three_consecutive_days():
    today = date.today()
    dates = {today, today - timedelta(days=1), today - timedelta(days=2)}
    assert calculate_streak(dates) == 3


def test_gap_breaks_streak_count_from_last_marked_day():
    today = date.today()
    # отметки позавчера и 5 дней назад — разрыв между ними не считается
    dates = {today - timedelta(days=1), today - timedelta(days=5)}
    assert calculate_streak(dates) == 1


def test_streak_reset_if_more_than_a_day_since_last_mark():
    today = date.today()
    dates = {today - timedelta(days=3), today - timedelta(days=4)}
    assert calculate_streak(dates) == 0
