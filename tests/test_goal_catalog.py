"""Каталог целей сфер (PRD 1.0, content/spheres/*.yaml) — схема и загрузчик
app/newlife/goal_catalog.py."""

import pytest
from pydantic import ValidationError

from app.newlife.goal_catalog import (
    SphereCatalog,
    all_goals,
    available_sphere_ids,
    goal_meta,
    load_all_catalogs,
)
from app.seasons_library.loader import load_library


ALL_SPHERE_IDS = [
    "body", "mind", "character", "social", "career", "finance",
    "relationships", "knowledge", "values", "lifestyle", "energy",
]

_MINIMAL_GUIDE = {
    "steps": [{"ru": "ш1", "uz": "q1"}, {"ru": "ш2", "uz": "q2"}, {"ru": "ш3", "uz": "q3"}],
    "mistakes": [{"ru": "о1", "uz": "x1"}, {"ru": "о2", "uz": "x2"}],
    "first_week_example": {"ru": "пример", "uz": "misol"},
}


def test_all_eleven_spheres_have_a_catalog_with_at_least_four_goals():
    catalogs = load_all_catalogs()
    for sphere_id in ALL_SPHERE_IDS:
        assert sphere_id in catalogs, f"нет каталога для сферы '{sphere_id}'"
        assert len(catalogs[sphere_id].goals) >= 4, f"'{sphere_id}': меньше 4 целей"


def test_no_duplicate_goal_ids_across_spheres():
    ids = [g.id for g in all_goals()]
    assert len(ids) == len(set(ids)), "повторяющийся id цели между разными сферами"


def test_every_goal_has_a_matching_season_template():
    """PRD 1.0: цель с прогрессией ссылается на реальный шаблон сезона."""
    library = load_library()
    for goal in all_goals():
        assert goal.template_id in library, f"{goal.id}: шаблон сезона '{goal.template_id}' не найден"


def test_every_goal_has_source_name_or_is_marked_heuristic():
    for goal in all_goals():
        assert goal.source.name
        if goal.source.is_heuristic:
            assert goal.source.url is None
        else:
            assert goal.source.url


def test_goal_meta_found_and_not_found():
    entry = goal_meta("muscle_gain")
    assert entry is not None
    assert entry.sphere == "body"
    assert goal_meta("does-not-exist") is None


def test_available_sphere_ids_covers_all_eleven_spheres():
    assert available_sphere_ids() == set(ALL_SPHERE_IDS)


def test_targets_has_one_to_three_options():
    for goal in all_goals():
        assert 1 <= len(goal.targets) <= 3, f"{goal.id}: targets должен быть 1-3 варианта"


def test_every_goal_has_a_complete_bilingual_guide():
    """Исправление «есть метрика, но нет ответа как именно это делать»:
    3-5 шагов, 2-3 частые ошибки, 1 пример первой недели, ru и uz заполнены."""
    for goal in all_goals():
        guide = goal.guide
        assert 3 <= len(guide.steps) <= 5, f"{goal.id}: guide.steps должен быть 3-5 шагов"
        assert 2 <= len(guide.mistakes) <= 3, f"{goal.id}: guide.mistakes должен быть 2-3 ошибки"
        for step in guide.steps:
            assert step.ru.strip(), f"{goal.id}: пустой шаг guide (ru)"
            assert step.uz.strip(), f"{goal.id}: пустой шаг guide (uz)"
        for mistake in guide.mistakes:
            assert mistake.ru.strip(), f"{goal.id}: пустая ошибка guide (ru)"
            assert mistake.uz.strip(), f"{goal.id}: пустая ошибка guide (uz)"
        assert guide.first_week_example.ru.strip(), f"{goal.id}: пустой first_week_example (ru)"
        assert guide.first_week_example.uz.strip(), f"{goal.id}: пустой first_week_example (uz)"


def test_ladder_present_only_for_confidence_and_public_speaking_goals():
    """Доп. задача (DECISIONS.md → guide/wger): лестницы 5-7 ступеней только
    у этих двух целей, остальные 65 — без ladder."""
    from app.newlife.goal_catalog import ladder_for_display

    ladder_goal_ids = {"confidence_through_action", "public_speaking_confidence"}
    for goal in all_goals():
        rungs = ladder_for_display(goal.id, "ru")
        if goal.id in ladder_goal_ids:
            assert rungs is not None
            assert 5 <= len(rungs) <= 7
            assert all(r.strip() for r in rungs)
        else:
            assert rungs is None, f"{goal.id}: неожиданно есть ladder"


def test_catalog_rejects_goal_sphere_mismatch():
    with pytest.raises(ValidationError):
        SphereCatalog.model_validate(
            {
                "sphere": "body",
                "goals": [
                    {
                        "id": "x",
                        "sphere": "mind",
                        "title": {"ru": "Х", "uz": "X"},
                        "difficulty": "d",
                        "for_whom": "f",
                        "outcome": "o",
                        "metric": {"key": "k", "kind": "counter", "unit": "u", "rounding": 1},
                        "targets": ["30 дней", "60 дней"],
                        "pace": "p",
                        "week_skeleton": "w",
                        "minimal_version": "m",
                        "guide": _MINIMAL_GUIDE,
                        "source": {"name": "s"},
                    }
                ],
            }
        )


def test_catalog_rejects_duplicate_goal_ids():
    goal = {
        "id": "dup",
        "sphere": "body",
        "title": {"ru": "Х", "uz": "X"},
        "difficulty": "d",
        "for_whom": "f",
        "outcome": "o",
        "metric": {"key": "k", "kind": "counter", "unit": "u", "rounding": 1},
        "targets": ["30 дней", "60 дней"],
        "pace": "p",
        "week_skeleton": "w",
        "minimal_version": "m",
        "guide": _MINIMAL_GUIDE,
        "source": {"name": "s"},
    }
    with pytest.raises(ValidationError):
        SphereCatalog.model_validate({"sphere": "body", "goals": [goal, goal]})
