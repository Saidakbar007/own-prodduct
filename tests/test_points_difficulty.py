"""Тесты сложности → очков (антиобман: клиент не может прислать свои очки)."""

from app.services.points import points_for_goal_difficulty, points_for_habit_difficulty


def test_habit_difficulty_points():
    assert points_for_habit_difficulty("easy") == 5
    assert points_for_habit_difficulty("medium") == 10
    assert points_for_habit_difficulty("hard") == 20
    assert points_for_habit_difficulty("unknown") == 10  # по умолчанию "средне"


def test_goal_difficulty_points():
    assert points_for_goal_difficulty("easy") == 50
    assert points_for_goal_difficulty("medium") == 100
    assert points_for_goal_difficulty("hard") == 200
    assert points_for_goal_difficulty("unknown") == 100
