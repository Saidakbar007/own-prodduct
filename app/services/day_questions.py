"""
"Вопрос дня" (PRD 1.0 F7): первые 7 дней после регистрации — по одному
вопросу в день на "Сегодня" из активных сфер. Банк — app/newlife/
question_bank.yaml. Ответ не пересчитывает точку А автоматически (вопросы
качественные, без прямого уровня 1-10, в отличие от point_a_rules.yaml) —
он просто записывается и виден человеку в "Я" → профиль, как и задумано
"уточнить картину", без скрытого алгоритма, которого нет в контент-доке.
"""

from datetime import date
from typing import Optional

from sqlmodel import Session, select

from app.models import DayQuestionAnswer, Profile, SphereState
from app.newlife.question_bank import DayQuestion, question_by_id, questions_for_sphere

FIRST_WEEK_DAYS = 7


def _day_number_since_onboarding(profile: Profile, today: date) -> Optional[int]:
    if not profile or not profile.onboarding_done_at:
        return None
    return (today - profile.onboarding_done_at.date()).days + 1


def _active_sphere_ids(db: Session, uid: int) -> list[str]:
    states = db.exec(
        select(SphereState).where(SphereState.uid == uid, SphereState.active.is_(True)).order_by(SphereState.sphere_id)
    ).all()
    return [s.sphere_id for s in states]


def answered_question_ids(db: Session, uid: int) -> set[str]:
    rows = db.exec(select(DayQuestionAnswer.question_id).where(DayQuestionAnswer.uid == uid)).all()
    return set(rows)


def todays_question(db: Session, uid: int, profile: Optional[Profile], today: date) -> Optional[DayQuestion]:
    """Вопрос на сегодня — None, если неделя первых вопросов прошла, уже
    ответил(а) сегодня, или для активных сфер вопросов не осталось."""
    day_number = _day_number_since_onboarding(profile, today) if profile else None
    if day_number is None or not (1 <= day_number <= FIRST_WEEK_DAYS):
        return None

    already_today = db.exec(
        select(DayQuestionAnswer.id).where(DayQuestionAnswer.uid == uid, DayQuestionAnswer.answered_on == today)
    ).first()
    if already_today:
        return None

    answered = answered_question_ids(db, uid)
    for sphere_id in _active_sphere_ids(db, uid):
        for question in questions_for_sphere(sphere_id):
            if question.id not in answered:
                return question
    return None


def record_answer(db: Session, uid: int, question_id: str, option_index: int, today: date) -> Optional[DayQuestionAnswer]:
    question = question_by_id(question_id)
    if not question or not (0 <= option_index < len(question.options)):
        return None
    answer = DayQuestionAnswer(
        uid=uid,
        question_id=question.id,
        sphere_id=question.sphere,
        option_index=option_index,
        option_text=question.options[option_index],
        answered_on=today,
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return answer


def recent_answers(db: Session, uid: int, limit: int = 20) -> list[DayQuestionAnswer]:
    """Для "Я" → профиль: что человек уже ответил на вопросы дня."""
    return db.exec(
        select(DayQuestionAnswer).where(DayQuestionAnswer.uid == uid).order_by(DayQuestionAnswer.answered_at.desc()).limit(limit)
    ).all()
