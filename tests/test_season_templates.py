"""Библиотека шаблонов сезонов (§5 Сезоны, §7 NewLife v8) — все 67 загружаются
и валидны: 11 целей "Тело" (5 исходных + activity_steps/sleep_consistency из
v8 + 4 новые 1.0: flexibility/nutrition/water/sitting_breaks) и по каждой из
10 остальных сфер — каталог content/spheres/<sphere>.yaml из Этапа 2 1.0
(см. docs/content/NEWLIFE_1_0_CONTENT.md)."""

import pytest

from app.seasons.engine import schedule_respects_safety
from app.seasons_library.loader import get_template, load_library

EXPECTED_IDS = {
    # Тело
    "run_5k", "pullups_10", "pushups_50", "fat_loss_safe", "muscle_gain",
    "activity_steps", "sleep_consistency", "flexibility", "nutrition",
    "water", "sitting_breaks",
    # Энергия и стресс
    "stress_relief_practice", "breathing_practice", "nature_time",
    "screen_off_before_sleep", "stable_wake_time",
    # Разум
    "deep_focus", "self_check_study", "memory_retention", "hard_tasks",
    "reading_minutes",
    # Знания
    "flashcards_mastered", "flashcards_streak", "online_course",
    "trivia_uzbekistan_world", "reading_notes",
    # Карьера и навыки
    "foreign_language", "vocabulary", "programming", "portfolio",
    "certificate", "resume_applications",
    # Характер
    "keep_promises", "if_then_plan", "deep_work", "beat_procrastination",
    "confidence_through_action", "responsibility_deadlines",
    # Социальное
    "public_speaking_confidence", "active_listening", "start_conversations",
    "networking", "presence_charisma", "keep_in_touch",
    # Ценности и дух
    "gratitude_journal", "gratitude_people", "weekly_reflection",
    "mindfulness", "live_by_values",
    # Финансы
    "expense_tracking", "budget", "savings", "emergency_fund",
    "income_growth", "financial_literacy",
    # Отношения
    "family", "friends", "partner_attention", "positive_communication",
    "new_connections", "calm_conflicts",
    # Образ жизни
    "digital_detox", "home_order", "hobby", "new_experiences",
    "style_and_care", "work_life_balance",
}


def test_library_has_exactly_sixty_seven_templates():
    assert set(load_library().keys()) == EXPECTED_IDS


@pytest.mark.parametrize("template_id", sorted(EXPECTED_IDS))
def test_template_is_internally_consistent(template_id):
    template = get_template(template_id)

    assert template.id == template_id
    assert template.phases[0].phase == 1
    assert template.measure_every_days > 0
    assert template.eligibility.min_age == 18
    assert all(p.days for p in template.phases)
    assert schedule_respects_safety(template), (
        f"{template_id}: расписание не оставляет минимум "
        f"{template.safety.rest_days_min_per_week} дней отдыха в неделю"
    )


def test_get_unknown_template_raises():
    with pytest.raises(KeyError):
        get_template("does-not-exist")


def test_fat_loss_safe_direction_is_down():
    template = get_template("fat_loss_safe")
    assert template.metric.direction == "down"


def test_multi_phase_templates_have_strictly_increasing_thresholds():
    """Для шаблонов с прогрессией ПО УРОВНЮ (baseline) пороги фаз должны
    строго расти. Исключение — время-последовательные шаблоны вроде
    fat_loss_safe, где все фазы имеют unlock_if_baseline_gte=0 и идут по
    времени, а не по baseline (см. engine.select_starting_phase docstring):
    у них все пороги равны, это осознанный выбор, а не баг."""
    for template_id, template in load_library().items():
        if len(template.phases) < 2:
            continue
        thresholds = [p.unlock_if_baseline_gte for p in template.phases]
        if len(set(thresholds)) == 1:
            continue
        assert thresholds == sorted(set(thresholds)), (
            f"{template_id}: пороги фаз должны строго расти"
        )
