"""Библиотека шаблонов сезонов (§5 ТЗ) — все 5 загружаются и валидны."""

import pytest

from app.seasons.engine import schedule_respects_safety
from app.seasons_library.loader import get_template, load_library

EXPECTED_IDS = {"run_5k", "pullups_10", "pushups_50", "fat_loss_safe", "muscle_gain"}


def test_library_has_exactly_five_templates():
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
    for template_id in ("run_5k", "pullups_10", "pushups_50"):
        template = get_template(template_id)
        thresholds = [p.unlock_if_baseline_gte for p in template.phases]
        assert thresholds == sorted(set(thresholds)), (
            f"{template_id}: пороги фаз должны строго расти"
        )
