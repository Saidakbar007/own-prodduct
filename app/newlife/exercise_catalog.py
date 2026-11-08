"""
Каталог базовых упражнений (доп. задача пользователя, см. docs/decisions/
DECISIONS.md → «Этап "Доделай" + guide + wger») — один общий YAML
`content/exercises.yaml` (не по сфере, в отличие от content/spheres/*.yaml:
упражнения общие для нескольких целей "Тело", дробить по сферам нет смысла).

Картинка (wger, только с разрешающей лицензией — автор/лицензия в
assets/photos/CREDITS.json) опциональна: без неё на экране показывается
схематичная SVG-иконка (app/static/icons/exercise_placeholder.svg), а не
дыра в интерфейсе.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field

_CONTENT_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "exercises.yaml"

Equipment = Literal["gym", "home"]


class ExerciseText(BaseModel):
    ru: str
    uz: str

    def text(self, lang: str) -> str:
        return self.uz if lang == "uz" else self.ru


class ExerciseEntry(BaseModel):
    id: str
    name: ExerciseText
    muscles: list[str] = Field(min_length=1)
    equipment: list[Equipment] = Field(min_length=1)
    technique: ExerciseText
    mistakes: list[ExerciseText] = Field(min_length=2, max_length=4)
    easy_version: ExerciseText
    hard_version: ExerciseText
    # id фото в assets/photos/exercises/ (см. CREDITS.json) — без картинки
    # показывается схематичная SVG-иконка, не дыра в интерфейсе.
    image: Optional[str] = None


@lru_cache(maxsize=1)
def load_exercises() -> dict[str, ExerciseEntry]:
    data = yaml.safe_load(_CONTENT_PATH.read_text(encoding="utf-8"))
    entries = [ExerciseEntry.model_validate(item) for item in data["exercises"]]
    ids = [e.id for e in entries]
    if len(set(ids)) != len(ids):
        raise ValueError("повторяющийся id упражнения в content/exercises.yaml")
    return {e.id: e for e in entries}


def exercise_meta(exercise_id: str) -> Optional[ExerciseEntry]:
    return load_exercises().get(exercise_id)


def all_exercises() -> list[ExerciseEntry]:
    return list(load_exercises().values())
