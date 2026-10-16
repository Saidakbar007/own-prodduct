"""
Юнит-тесты streak с заморозкой и честными пропусками (чистая функция).
Используем фиксированную дату "сегодня" (среда), чтобы тесты не зависели
от дня недели, в который реально запускаются.
"""

from datetime import date, timedelta

from app.services.streak import calculate_streak_with_freeze, consecutive_run_from

FIXED_TODAY = date(2026, 1, 16)  # пятница — пропуски в 1-3 дня назад не пересекают границу недели


def test_no_gaps_simple_streak():
    done = {FIXED_TODAY, FIXED_TODAY - timedelta(days=1), FIXED_TODAY - timedelta(days=2)}
    result = calculate_streak_with_freeze(done, set(), today=FIXED_TODAY)
    assert result["streak"] == 3
    assert result["freezes_left"] == 2


def test_honest_skip_does_not_break_or_grow_streak():
    done = {FIXED_TODAY, FIXED_TODAY - timedelta(days=2)}
    skip = {FIXED_TODAY - timedelta(days=1)}
    result = calculate_streak_with_freeze(done, skip, today=FIXED_TODAY)
    assert result["streak"] == 2  # сегодня + 2 дня назад, вчерашний skip не прерывает и не увеличивает


def test_missing_day_consumes_a_freeze():
    done = {FIXED_TODAY, FIXED_TODAY - timedelta(days=2)}  # вчера пропущено молча
    result = calculate_streak_with_freeze(done, set(), today=FIXED_TODAY)
    assert result["streak"] == 2
    assert result["freezes_left"] == 1  # одна заморозка потрачена на эту неделю


def test_streak_breaks_when_freezes_exhausted():
    # Между двумя реальными отметками (today и today-4) — разрыв в 3 дня,
    # это больше, чем доступные 2 заморозки в неделю.
    done = {FIXED_TODAY, FIXED_TODAY - timedelta(days=4)}
    result = calculate_streak_with_freeze(done, set(), max_freezes_per_week=2, today=FIXED_TODAY)
    assert result["streak"] == 1  # до today-4 серия не дотягивается
    assert result["freezes_left"] == 0


def test_bonus_freeze_extends_streak_further():
    done = {FIXED_TODAY, FIXED_TODAY - timedelta(days=4)}

    # без бонуса: 2 заморозки не покрывают дыру в 3 дня (today-1..today-3)
    result_without = calculate_streak_with_freeze(done, set(), today=FIXED_TODAY)
    assert result_without["streak"] == 1

    iso_year, iso_week, _ = FIXED_TODAY.isocalendar()
    week_key = f"{iso_year}-W{iso_week:02d}"

    # +1 бонусная заморозка на эту неделю (итого 3) — серия дотягивается до today-4
    result_with = calculate_streak_with_freeze(done, set(), bonus_freezes={week_key: 1}, today=FIXED_TODAY)
    assert result_with["streak"] == 2


def test_consecutive_run_from_detects_break():
    start = FIXED_TODAY - timedelta(days=4)
    done = {start, start + timedelta(days=1), start + timedelta(days=3)}  # пропуск на 3-й день
    length, broken = consecutive_run_from(done, start, FIXED_TODAY)
    assert length == 2
    assert broken is True


def test_consecutive_run_from_full_run():
    start = FIXED_TODAY - timedelta(days=2)
    done = {start, start + timedelta(days=1), start + timedelta(days=2)}
    length, broken = consecutive_run_from(done, start, FIXED_TODAY)
    assert length == 3
    assert broken is False
