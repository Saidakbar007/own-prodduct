"""Юнит-тесты ядра app/seasons/engine.py — таблицами случаев (§6 ТЗ)."""

from datetime import date

import pytest

from app.seasons import engine
from app.seasons.schema import (
    BaselineTest,
    Eligibility,
    Measure,
    Metric,
    Phase,
    RestDay,
    Safety,
    Schedule,
    SeasonDayTemplate,
    SeasonTemplate,
)
from app.seasons_library.loader import get_template


def _day(expected_progress=1.0, title="T") -> SeasonDayTemplate:
    return SeasonDayTemplate(
        title=title, instructions="i", minimal="m", expected_progress=expected_progress
    )


def make_template(phases: list[tuple[int, float]], measure_every_days=7) -> SeasonTemplate:
    """Синтетический шаблон для тестов движка — без привязки к библиотеке."""
    return SeasonTemplate(
        id="synthetic",
        version=1,
        title="Синтетика",
        category="fitness",
        metric=Metric(name="X", unit="ед", direction="up"),
        lengths=[30, 60, 90],
        target_default=10,
        baseline_test=BaselineTest(prompt="?", input="number", min=0, max=100),
        eligibility=Eligibility(),
        schedule=Schedule(train_days=[1, 3, 5], minutes=[20, 30]),
        phases=[Phase(phase=num, unlock_if_baseline_gte=thr, days=[_day()]) for num, thr in phases],
        rest_day=RestDay(title="Отдых", instructions="гуляй"),
        measure_every_days=measure_every_days,
        measure=Measure(prompt="Сколько?"),
        safety=Safety(max_phase_jump=1, rest_days_min_per_week=1),
    )


# ------------------------------------------------------------- select_starting_phase

@pytest.mark.parametrize(
    "baseline,expected_phase",
    [
        (0, 1),
        (4.9, 1),
        (5, 2),
        (9, 2),
        (10, 3),
        (999, 3),
    ],
)
def test_select_starting_phase_distinct_thresholds(baseline, expected_phase):
    template = make_template([(1, 0), (2, 5), (3, 10)])
    assert engine.select_starting_phase(template, baseline).phase == expected_phase


def test_select_starting_phase_ties_pick_the_first():
    # fat_loss_safe/muscle_gain: несколько фаз с одинаковым порогом 0 —
    # прогрессия по времени/замерам, а не по тесту уровня.
    template = make_template([(1, 0), (2, 0), (3, 0)])
    assert engine.select_starting_phase(template, 50).phase == 1


# ------------------------------------------------------------------ adapt_phase

@pytest.mark.parametrize(
    "measured,expected,current,result",
    [
        (10, 10, 2, 2),  # ровно ожидаемое — без изменений
        (11.4, 10, 2, 2),  # +14% — в пределах порога
        (11.6, 10, 2, 3),  # +16% — на фазу вперёд
        (8.6, 10, 2, 2),  # -14% (0.86 > 0.85) — в пределах порога, без изменений
        (8.4, 10, 2, 1),  # -16% (0.84 <= 0.85) — на фазу назад
    ],
)
def test_adapt_phase_thresholds(measured, expected, current, result):
    template = make_template([(1, 0), (2, 0), (3, 0)])
    assert engine.adapt_phase(template, current, measured, expected, max_phase_jump=1) == result


def test_adapt_phase_does_not_go_below_first_or_above_last_phase():
    template = make_template([(1, 0), (2, 0)])
    assert engine.adapt_phase(template, 1, 5, 10, max_phase_jump=1) == 1  # -50%, но дальше некуда
    assert engine.adapt_phase(template, 2, 20, 10, max_phase_jump=1) == 2  # +100%, но дальше некуда


def test_adapt_phase_zero_expected_is_noop():
    template = make_template([(1, 0), (2, 0)])
    assert engine.adapt_phase(template, 1, 5, 0, max_phase_jump=1) == 1


# ---------------------------------------------------------- schedule_respects_safety

def test_schedule_respects_safety_true_when_enough_rest():
    template = make_template([(1, 0)])  # train_days=[1,3,5] -> 4 дня отдыха, safety=1
    assert engine.schedule_respects_safety(template) is True


def test_schedule_respects_safety_false_when_not_enough_rest():
    template = make_template([(1, 0)])
    template.schedule.train_days = [1, 2, 3, 4, 5, 6, 7]  # без единого дня отдыха
    assert engine.schedule_respects_safety(template) is False


@pytest.mark.parametrize("template_id", ["run_5k", "pullups_10", "pushups_50", "fat_loss_safe", "muscle_gain"])
def test_library_templates_respect_safety(template_id):
    assert engine.schedule_respects_safety(get_template(template_id)) is True


# ----------------------------------------------------------- week_bucket_start

@pytest.mark.parametrize(
    "reference,expected",
    [
        (date(2026, 11, 2), date(2026, 11, 2)),  # понедельник -> сам себе бакет
        (date(2026, 11, 3), date(2026, 11, 2)),  # вторник -> понедельник той же недели
        (date(2026, 11, 8), date(2026, 11, 2)),  # воскресенье -> понедельник той же недели
    ],
)
def test_week_bucket_start(reference, expected):
    assert engine.week_bucket_start(reference) == expected


# ------------------------------------------------------------- второй шанс

@pytest.mark.parametrize(
    "length_days,expected",
    [(30, 3), (60, 6), (90, 9)],
)
def test_second_chances_for_length(length_days, expected):
    assert engine.second_chances_for_length(length_days) == expected


def test_can_rescue_day_within_window():
    missed = date(2026, 11, 5)
    assert engine.can_rescue_day(missed, missed) is True
    assert engine.can_rescue_day(missed, missed.replace(day=6)) is True
    assert engine.can_rescue_day(missed, missed.replace(day=7)) is False
    assert engine.can_rescue_day(missed, missed.replace(day=4)) is False


# --------------------------------------------------------------- build_season_days

def test_build_season_days_assigns_kinds_by_schedule():
    template = make_template([(1, 0)], measure_every_days=7)
    start = date(2026, 11, 2)  # понедельник
    days = engine.build_season_days(template, template.phases[0], start, length_days=10, weekdays=[1, 3, 5])

    assert len(days) == 10
    kinds = {d.day_number: d.kind for d in days}
    assert kinds[1] == "measure"  # день 1 — всегда точка старта (пролога нет)
    assert kinds[2] == "rest"  # вторник — не входит в [1,3,5]
    assert kinds[3] == "train"  # первый обычный тренировочный день
    assert kinds[7] == "measure"  # кратно measure_every_days
    assert kinds[10] == "measure"  # финал — всегда замер


def test_build_season_days_supports_rolling_window():
    template = make_template([(1, 0)])
    start = date(2026, 11, 2)
    partial = engine.build_season_days(
        template, template.phases[0], start, length_days=30, weekdays=[1, 3, 5], until_day_number=14
    )
    assert len(partial) == 14
    assert partial[-1].day_number == 14


def test_build_season_days_cycles_through_multiple_day_templates():
    template = make_template([(1, 0)])
    template.phases[0].days = [_day(title="A"), _day(title="B")]
    start = date(2026, 11, 2)
    # length_days=6: день 1 принудительно "точка старта" (measure), день 6 —
    # финал (тоже measure), поэтому из расписания [1,3,5] тренировочные
    # остаются только дни 3 и 5.
    days = engine.build_season_days(template, template.phases[0], start, length_days=6, weekdays=[1, 3, 5])
    train_titles = [d.title for d in days if d.kind == "train"]
    assert train_titles == ["A", "B"]


# ------------------------------------------------------------------ result_tier

@pytest.mark.parametrize(
    "statuses,expected",
    [
        (["done"] * 20, "clean"),
        (["done"] * 19 + ["rescued"], "clean"),
        # ровно 95% done и единственный missed без пары подряд — порог
        # "без missed подряд" не нарушен, доля всё ещё clean
        (["done"] * 19 + ["missed"], "clean"),
    ],
)
def test_result_tier_examples(statuses, expected):
    assert engine.result_tier(statuses) == expected


def test_result_tier_clean_requires_95_percent_done_or_rescued():
    statuses = ["done"] * 18 + ["minimal"] * 2  # 18/20 = 90% строго done -> не clean
    assert engine.result_tier(statuses) == "passed"


def test_result_tier_consecutive_missed_blocks_clean_even_at_95_percent():
    statuses = ["done"] * 18 + ["missed", "missed"]  # 90% done, и два missed подряд
    assert engine.result_tier(statuses) == "passed"


def test_result_tier_passed_counts_minimal_as_half():
    # 15 done (75%) + 10 minimal (по 0.5 = 5) из 20 -> (15+5)/20 = 100% -> экстремально высоко, тест на честность половины:
    statuses = ["done"] * 10 + ["minimal"] * 10  # (10 + 5) / 20 = 75%
    assert engine.result_tier(statuses) == "passed"


def test_result_tier_below_75_percent_is_completed():
    statuses = ["done"] * 5 + ["missed"] * 15
    assert engine.result_tier(statuses) == "completed"


def test_result_tier_ignores_rest_days():
    statuses = ["done"] * 19 + ["rescued"] + ["rest"] * 5
    assert engine.result_tier(statuses) == "clean"


def test_result_tier_empty_season_is_completed():
    assert engine.result_tier([]) == "completed"
    assert engine.result_tier(["rest", "rest"]) == "completed"


# --------------------------------------------------------------- adherence_14d

def test_adherence_14d_perfect():
    assert engine.adherence_14d(["done"] * 6) == 1.0


def test_adherence_14d_with_minimal_and_missed():
    # 2 done + 1 minimal(0.5) + 1 missed из 4 -> 2.5/4
    assert engine.adherence_14d(["done", "done", "minimal", "missed"]) == pytest.approx(0.625)


def test_adherence_14d_no_planned_days_is_full_adherence():
    assert engine.adherence_14d(["rest", "rest"]) == 1.0


# ---------------------------------------------------------------------- прогноз

def test_forecast_by_plan_linear():
    value = engine.forecast_by_plan(
        current_value=10, remaining_sessions=5, expected_progress_per_session=1.0, adherence=0.8
    )
    assert value == pytest.approx(10 + 5 * 1.0 * 0.8)


def test_forecast_by_measurements_needs_at_least_two_points():
    assert engine.forecast_by_measurements([5.0], remaining_weeks=4) is None
    assert engine.forecast_by_measurements([], remaining_weeks=4) is None


def test_forecast_by_measurements_extrapolates_trend():
    # Идеальная прямая: +2 за неделю замеров -> через 3 недели вперёд +6
    values = [10, 12, 14, 16]
    result = engine.forecast_by_measurements(values, remaining_weeks=3)
    assert result == pytest.approx(16 + 2 * 3)


def test_forecast_result_falls_back_to_plan_with_few_measurements():
    plan_only = engine.forecast_result(
        current_value=10,
        remaining_sessions=5,
        expected_progress_per_session=1.0,
        adherence=1.0,
        measurement_values=[10.0],
        remaining_weeks=2,
    )
    assert plan_only == pytest.approx(15.0)


def test_forecast_result_blends_plan_and_measurements():
    result = engine.forecast_result(
        current_value=10,
        remaining_sessions=5,
        expected_progress_per_session=1.0,
        adherence=1.0,
        measurement_values=[10, 12, 14, 16],
        remaining_weeks=3,
    )
    plan = 15.0
    measured = 22.0
    assert result == pytest.approx(0.4 * plan + 0.6 * measured)


# -------------------------------------------------------------------- безопасность

def test_safe_weekly_change_limit():
    assert engine.safe_weekly_change_limit("down") == 0.01
    assert engine.safe_weekly_change_limit("up") == 0.005


def test_clamp_weight_target_blocks_too_fast_loss():
    # 80 кг, хотят -16 кг за 8 недель (2 кг/нед = 2.5%/нед) -> должно урезаться до 1%/нед * 8 = 6.4 кг
    clamped = engine.clamp_weight_target(baseline_value=80, raw_target_value=64, direction="down", weeks=8)
    assert clamped == pytest.approx(80 - 80 * 0.01 * 8)


def test_clamp_weight_target_allows_safe_goal():
    # -4 кг за 8 недель (0.5%/нед) — безопасно, не трогаем
    clamped = engine.clamp_weight_target(baseline_value=80, raw_target_value=76, direction="down", weeks=8)
    assert clamped == pytest.approx(76)


def test_clamp_weight_target_blocks_too_fast_gain():
    clamped = engine.clamp_weight_target(baseline_value=70, raw_target_value=80, direction="up", weeks=8)
    assert clamped == pytest.approx(70 + 70 * 0.005 * 8)


def test_clamp_weight_target_noop_for_zero_weeks_or_baseline():
    assert engine.clamp_weight_target(80, 64, "down", weeks=0) == 64
    assert engine.clamp_weight_target(0, 64, "down", weeks=8) == 64


# ---------------------------------------------------------------------------- BMI

@pytest.mark.parametrize(
    "weight,height,eligible",
    [
        (70, 175, True),  # BMI ~22.9
        (55, 175, False),  # BMI ~18.0 < 18.5
        (56.7, 175, True),  # BMI ~18.5 ровно на границе
    ],
)
def test_meets_fat_loss_eligibility(weight, height, eligible):
    assert engine.meets_fat_loss_eligibility(weight, height) is eligible


def test_bmi_rejects_non_positive_height():
    with pytest.raises(ValueError):
        engine.bmi(70, 0)
