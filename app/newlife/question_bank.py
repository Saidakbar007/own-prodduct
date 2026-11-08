"""
Банк "вопрос дня" (PRD 1.0 F7) — один YAML `question_bank.yaml`, ключ
верхнего уровня — id сферы, значение — список вопросов с кнопками-вариантами
(никакого текстового ввода). Схема и загрузчик с кэшем, по образцу
app/newlife/habit_catalog.py.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

from app.newlife.spheres import SPHERE_IDS

_PATH = Path(__file__).parent / "question_bank.yaml"


class DayQuestion(BaseModel):
    id: str
    sphere: str
    text: str
    options: list[str] = Field(min_length=2, max_length=6)


@lru_cache(maxsize=1)
def load_question_bank() -> dict[str, list[DayQuestion]]:
    """Все вопросы, ключ — id сферы. Падает на невалидном YAML/неизвестной
    сфере/дублирующемся id — это контент, который правит человек, а не
    код, ошибка должна быть видна сразу, а не тихо проезжать в прод."""
    raw = yaml.safe_load(_PATH.read_text(encoding="utf-8")) or {}
    bank: dict[str, list[DayQuestion]] = {}
    seen_ids: set[str] = set()
    for sphere_id, entries in raw.items():
        if sphere_id not in SPHERE_IDS:
            raise ValueError(f"question_bank.yaml: неизвестная сфера '{sphere_id}'")
        questions = []
        for entry in entries:
            question = DayQuestion.model_validate({**entry, "sphere": sphere_id})
            if question.id in seen_ids:
                raise ValueError(f"question_bank.yaml: повторяющийся id вопроса '{question.id}'")
            seen_ids.add(question.id)
            questions.append(question)
        bank[sphere_id] = questions
    return bank


def questions_for_sphere(sphere_id: str) -> list[DayQuestion]:
    return load_question_bank().get(sphere_id, [])


def all_questions() -> list[DayQuestion]:
    questions: list[DayQuestion] = []
    for sphere_questions in load_question_bank().values():
        questions.extend(sphere_questions)
    return questions


def question_by_id(question_id: str) -> Optional[DayQuestion]:
    for question in all_questions():
        if question.id == question_id:
            return question
    return None
