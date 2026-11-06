"""Банк "вопрос дня" (PRD 1.0 F7) — схема и загрузчик app/newlife/question_bank.py."""

from app.newlife.question_bank import all_questions, load_question_bank, question_by_id, questions_for_sphere
from app.newlife.spheres import SPHERE_IDS


def test_every_sphere_has_at_least_three_questions():
    bank = load_question_bank()
    for sphere_id in SPHERE_IDS:
        assert sphere_id in bank, f"нет вопросов для сферы '{sphere_id}'"
        assert len(bank[sphere_id]) >= 3, f"'{sphere_id}': меньше 3 вопросов дня"


def test_every_question_has_two_to_six_options():
    for question in all_questions():
        assert 2 <= len(question.options) <= 6


def test_no_duplicate_question_ids():
    ids = [q.id for q in all_questions()]
    assert len(ids) == len(set(ids))


def test_questions_for_sphere_matches_sphere_field():
    for question in questions_for_sphere("body"):
        assert question.sphere == "body"


def test_question_by_id_found_and_not_found():
    question = question_by_id("body_water_today")
    assert question is not None
    assert question.sphere == "body"
    assert question_by_id("does-not-exist") is None
