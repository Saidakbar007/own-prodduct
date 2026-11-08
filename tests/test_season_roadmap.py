"""Роудмап-«тропа» детальной страницы сезона (NEWLIFE_2_0.md §3.2, Задача 3) —
только для сфер Тело/Разум/Энергия (app/routers/season.py::_build_roadmap).
Для богатых прогрессий (run_5k — 5 фаз) шаг = фаза шаблона; для шаблонов с
одной фазой (сейчас все Mind/Energy) — тропа по неделям сезона."""

from types import SimpleNamespace

from app.routers.season import _build_roadmap


def _season(template_id: str, current_phase: int = 1, length_days: int = 60) -> SimpleNamespace:
    return SimpleNamespace(template_id=template_id, current_phase=current_phase, length_days=length_days)


def test_roadmap_none_for_spheres_outside_body_mind_energy():
    # programming — сфера "career", роудмап не строится (задача 3: только 3 сферы).
    assert _build_roadmap(_season("programming"), today_number=1, lang="ru") is None


def test_roadmap_multi_phase_run_5k_marks_current_phase():
    roadmap = _build_roadmap(_season("run_5k", current_phase=3, length_days=90), today_number=40, lang="ru")
    assert roadmap is not None
    assert roadmap["sphere_id"] == "body"
    assert roadmap["total"] == 5
    assert roadmap["current_number"] == 3
    statuses = [s["status"] for s in roadmap["steps"]]
    assert statuses == ["done", "done", "here", "future", "future"]
    # Шаги упорядочены и дни возрастают.
    days = [s["days_label"] for s in roadmap["steps"]]
    assert len(days) == 5


def test_roadmap_single_phase_mind_falls_back_to_weeks():
    # deep_focus (mind) — всего 1 фаза в YAML, значит тропа строится по неделям.
    roadmap = _build_roadmap(_season("deep_focus", current_phase=1, length_days=60), today_number=10, lang="ru")
    assert roadmap is not None
    assert roadmap["sphere_id"] == "mind"
    assert roadmap["total"] == 9  # ceil(60/7)
    assert roadmap["current_number"] == 2  # ceil(10/7)
    statuses = [s["status"] for s in roadmap["steps"]]
    assert statuses[0] == "done"
    assert statuses[1] == "here"
    assert statuses[2] == "future"


def test_roadmap_single_phase_energy_falls_back_to_weeks():
    # breathing_practice (energy) — тоже 1 фаза, та же логика недель.
    roadmap = _build_roadmap(_season("breathing_practice", current_phase=1, length_days=30), today_number=1, lang="ru")
    assert roadmap is not None
    assert roadmap["sphere_id"] == "energy"
    assert roadmap["total"] == 5  # ceil(30/7)
    assert roadmap["current_number"] == 1
