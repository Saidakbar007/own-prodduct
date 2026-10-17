"""Тесты названия ранга по сумме очков — через новую систему уровней (v6a)."""

from app.services.levels import level_for_xp, rank_for_level
from app.services.points import level_name_for_points


def test_level_name_for_points_delegates_to_rank_system():
    for points in (0, 50, 150, 400, 700, 1500, 5000, 50000):
        assert level_name_for_points(points) == rank_for_level(level_for_xp(points))


def test_rank_boundaries_by_points():
    assert level_name_for_points(0) == "Новичок"
    assert level_for_xp(0) == 1
    # уровень 6 (начало ранга "Ученик") достигается ровно на 700 XP
    assert level_name_for_points(699) == "Новичок"
    assert level_name_for_points(700) == "Ученик"
