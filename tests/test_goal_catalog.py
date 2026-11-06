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
        "source": {"name": "s"},
    }
    with pytest.raises(ValidationError):
        SphereCatalog.model_validate({"sphere": "body", "goals": [goal, goal]})
