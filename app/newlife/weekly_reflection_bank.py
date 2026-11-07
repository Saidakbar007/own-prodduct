"""
Недельная рефлексия (доп. задача, см. docs/decisions/DECISIONS.md →
«Этап "Доделай" + guide + wger»): 5 фиксированных вопросов кнопками, один
раз в неделю. `app/newlife/weekly_reflection.yaml`, схема и загрузчик с
кэшем — по образцу app/newlife/question_bank.py, но с ru/uz (тот банк
построен раньше и был только на русском).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

_PATH = Path(__file__).parent / "weekly_reflection.yaml"


class ReflectionOption(BaseModel):
    ru: str
    uz: str

    def text(self, lang: str) -> str:
        return self.uz if lang == "uz" else self.ru


class ReflectionQuestion(BaseModel):
    id: str
    text: ReflectionOption
    options: list[ReflectionOption] = Field(min_length=2, max_length=6)


@lru_cache(maxsize=1)
def load_weekly_reflection() -> list[ReflectionQuestion]:
    data = yaml.safe_load(_PATH.read_text(encoding="utf-8"))
    questions = [ReflectionQuestion.model_validate(q) for q in data["questions"]]
    ids = [q.id for q in questions]
    if len(set(ids)) != len(ids):
        raise ValueError("повторяющийся id вопроса в weekly_reflection.yaml")
    return questions


def question_meta(question_id: str) -> ReflectionQuestion | None:
    for q in load_weekly_reflection():
        if q.id == question_id:
            return q
    return None
