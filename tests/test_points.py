"""Тесты очков и уровней (пороги Новичок/Ученик/Практик/Мастер/Легенда)."""

from app.services.points import level_name_for_points


def test_level_thresholds():
    assert level_name_for_points(0) == "Новичок"
    assert level_name_for_points(99) == "Новичок"
    assert level_name_for_points(100) == "Ученик"
    assert level_name_for_points(299) == "Ученик"
    assert level_name_for_points(300) == "Практик"
    assert level_name_for_points(699) == "Практик"
    assert level_name_for_points(700) == "Мастер"
    assert level_name_for_points(1499) == "Мастер"
    assert level_name_for_points(1500) == "Легенда"
    assert level_name_for_points(99999) == "Легенда"
