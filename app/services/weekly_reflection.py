"""
Недельная рефлексия (доп. задача, см. docs/decisions/DECISIONS.md →
«Этап "Доделай" + guide + wger»): 5 фиксированных вопросов кнопками, по
одному разу на каждый вопрос в текущей неделе пользователя (понедельник —
воскресенье, по его часовому поясу). Банк — app/newlife/weekly_reflection.yaml.
"""

from datetime import date, timedelta
from typing import Optional

from sqlmodel import Session, select

from app.models import WeeklyReflectionAnswer
from app.newlife.weekly_reflection_bank import ReflectionQuestion, load_weekly_reflection, question_meta


def week_start(today: date) -> date:
    """Понедельник недели, содержащей `today`."""
    return today - timedelta(days=today.weekday())


def answered_question_ids_this_week(db: Session, uid: int, today: date) -> set[str]:
    rows = db.exec(
        select(WeeklyReflectionAnswer.question_id).where(
            WeeklyReflectionAnswer.uid == uid,
            WeeklyReflectionAnswer.week_start == week_start(today),
        )
    ).all()
    return set(rows)


def next_question(db: Session, uid: int, today: date) -> Optional[ReflectionQuestion]:
    """Первый неотвеченный вопрос этой недели; None — если все 5 уже
    отвечены на этой неделе."""
    answered = answered_question_ids_this_week(db, uid, today)
    for question in load_weekly_reflection():
        if question.id not in answered:
            return question
    return None


def record_answer(db: Session, uid: int, question_id: str, option_index: int, today: date) -> Optional[WeeklyReflectionAnswer]:
    question = question_meta(question_id)
    if not question or not (0 <= option_index < len(question.options)):
        return None
    answer = WeeklyReflectionAnswer(
        uid=uid,
        question_id=question.id,
        option_index=option_index,
        option_text=question.options[option_index].ru,
        week_start=week_start(today),
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return answer


def recent_answers(db: Session, uid: int, limit: int = 20) -> list[WeeklyReflectionAnswer]:
    """Для "Я" → профиль."""
    return db.exec(
        select(WeeklyReflectionAnswer)
        .where(WeeklyReflectionAnswer.uid == uid)
        .order_by(WeeklyReflectionAnswer.answered_at.desc())
        .limit(limit)
    ).all()
