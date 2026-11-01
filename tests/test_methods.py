"""Методы саморазвития как правила (§9 NEWLIFE_V8_SPEC.md) — детекция триггеров."""

from datetime import date

from app.newlife import methods as m


def test_methods_catalog_has_all_twelve_with_sources():
    assert len(m.METHODS) == 12
    for method in m.METHODS:
        assert method.name
        assert method.trigger
        assert method.source


def test_method_by_id_lookup():
    assert m.METHOD_BY_ID["woop"].source == "Oettingen"


def test_recovery_mode_triggered_by_three_misses_in_week():
    assert m.should_suggest_recovery_mode(3, [4, 4, 4]) is True
    assert m.should_suggest_recovery_mode(2, [4, 4, 4]) is False


def test_recovery_mode_triggered_by_three_low_energy_days_in_a_row():
    assert m.should_suggest_recovery_mode(0, [3, 2, 2, 2]) is True
    assert m.should_suggest_recovery_mode(0, [1, 2, 3]) is False  # не подряд низкая


def test_recovery_mode_not_triggered_with_too_few_energy_readings():
    assert m.should_suggest_recovery_mode(0, [2, 2]) is False


def test_anchor_suggested_only_for_forget_obstacle_with_two_misses():
    assert m.should_suggest_anchor(2, "forget") is True
    assert m.should_suggest_anchor(1, "forget") is False
    assert m.should_suggest_anchor(2, "tired") is False
    assert m.should_suggest_anchor(2, None) is False


def test_dont_skip_twice_nudge_on_missed_or_unlogged_yesterday():
    assert m.should_show_dont_skip_twice_nudge("missed") is True
    assert m.should_show_dont_skip_twice_nudge(None) is True
    assert m.should_show_dont_skip_twice_nudge("done") is False


def test_stress_talk_suggested_after_seven_high_stress_days():
    assert m.should_suggest_stress_talk([4] * 7) is True
    assert m.should_suggest_stress_talk([4] * 6 + [3]) is False
    assert m.should_suggest_stress_talk([4] * 6) is False  # меньше 7 значений


def test_sleep_hygiene_reminder_in_60_minute_window_before_bedtime():
    sleep_at = 23 * 60  # 23:00
    assert m.should_show_sleep_hygiene_reminder(22 * 60 + 30, sleep_at) is True
    assert m.should_show_sleep_hygiene_reminder(21 * 60 + 59, sleep_at) is False
    assert m.should_show_sleep_hygiene_reminder(sleep_at, sleep_at) is False  # уже отбой


def test_temptation_bundling_suggested_on_boredom_trigger():
    assert m.should_suggest_temptation_bundling(["boredom"]) is True
    assert m.should_suggest_temptation_bundling(["stress", "tiredness"]) is False


def test_recovery_mode_active_window():
    start = date(2026, 11, 2)
    assert m.is_recovery_mode_active(start, date(2026, 11, 2), True) is True
    assert m.is_recovery_mode_active(start, date(2026, 11, 8), True) is True
    assert m.is_recovery_mode_active(start, date(2026, 11, 9), True) is False
    assert m.is_recovery_mode_active(start, date(2026, 11, 5), False) is False
