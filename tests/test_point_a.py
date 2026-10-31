"""Правила перевода ответов онбординга в уровень точки А (§5)."""

from app.newlife import point_a
from app.newlife.spheres import SPHERE_IDS


def test_every_sphere_has_a_question():
    rules = point_a.load_point_a_rules()
    assert set(rules.keys()) == set(SPHERE_IDS)


def test_every_question_has_at_least_two_options_with_valid_levels():
    rules = point_a.load_point_a_rules()
    for sphere_id, question in rules.items():
        assert len(question.options) >= 2, sphere_id
        for opt in question.options:
            assert 1 <= opt.level <= 10, sphere_id


def test_level_for_answer_returns_matching_option():
    q = point_a.question_for("body")
    assert point_a.level_for_answer("body", 0) == q.options[0].level
    assert point_a.level_for_answer("body", len(q.options) - 1) == q.options[-1].level


def test_level_for_answer_out_of_range_is_none():
    assert point_a.level_for_answer("body", 999) is None
    assert point_a.level_for_answer("body", -1) is None
