"""
Программы силовых тренировок новичка (доп. задача, см. docs/decisions/
DECISIONS.md → «Этап "Доделай" + guide + wger»): `content/workout_programs.yaml`,
2 программы (зал/дом) по ACSM, каждая — фиксированный список упражнений из
`app/newlife/exercise_catalog.py`.

Не трогает существующие SeasonTemplate (app/seasons_library/*.yaml) —
фазы/прогрессия muscle_gain и fat_loss_safe остаются как были (§7
NEWLIFE_V8_SPEC, уже покрыты тестами). Программа — это ДОПОЛНИТЕЛЬНЫЙ,
более подробный экран (/workout) для дней тренировки этих целей: список
конкретных упражнений с картинкой/техникой и полями вес/повторы, вместо
(или в дополнение к) обычной кнопки "Сделал". Какие цели это затрагивает —
WORKOUT_PROGRAM_GOALS ниже, сознательно не muscle_gain-специфичный текст
фаз, а общий фулбади-список для новичка.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field

from app.newlife.exercise_catalog import load_exercises

_CONTENT_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "workout_programs.yaml"

Equipment = Literal["gym", "home"]

# Цели, у которых день тренировки открывается как программа (/workout), а не
# просто текстовая инструкция. "Сила" из пожелания пользователя не нашлась
# отдельной целью каталога (см. DECISIONS.md) — ближе всего muscle_gain;
# pullups_10/pushups_50 оставлены со своей специфической прогрессией одного
# упражнения, им общий фулбади-список не подходит.
WORKOUT_PROGRAM_GOALS = {"muscle_gain", "fat_loss_safe"}


class ProgramText(BaseModel):
    ru: str
    uz: str

    def text(self, lang: str) -> str:
        return self.uz if lang == "uz" else self.ru


class WorkoutProgram(BaseModel):
    id: str
    title: ProgramText
    equipment: Equipment
    sets: int = Field(gt=0)
    reps_range: str
    rest_minutes: str
    progression: ProgramText
    exercises: list[str] = Field(min_length=1)


@lru_cache(maxsize=1)
def load_programs() -> dict[str, WorkoutProgram]:
    data = yaml.safe_load(_CONTENT_PATH.read_text(encoding="utf-8"))
    programs = [WorkoutProgram.model_validate(item) for item in data["programs"]]
    known_exercise_ids = set(load_exercises().keys())
    for program in programs:
        unknown = [e for e in program.exercises if e not in known_exercise_ids]
        if unknown:
            raise ValueError(f"{program.id}: неизвестные упражнения {unknown}")
    return {p.id: p for p in programs}


def program_meta(program_id: str) -> Optional[WorkoutProgram]:
    return load_programs().get(program_id)


def program_for_goal(goal_id: str, equipment: Equipment) -> Optional[WorkoutProgram]:
    """Программа для цели и выбранного инвентаря (зал/дом); None — если у
    этой цели нет программы (goal_id не в WORKOUT_PROGRAM_GOALS)."""
    if goal_id not in WORKOUT_PROGRAM_GOALS:
        return None
    program_id = "full_body_gym" if equipment == "gym" else "full_body_home"
    return program_meta(program_id)
