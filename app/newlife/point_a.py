"""
Загрузка и валидация app/newlife/point_a_rules.yaml (§5): один вопрос
уровня на сферу, 4 варианта, каждый — число уровня 1..10.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, RootModel

from app.newlife.spheres import SPHERE_IDS

_PATH = Path(__file__).parent / "point_a_rules.yaml"


class LevelOption(BaseModel):
    label: str
    level: int = Field(ge=1, le=10)


class LevelQuestion(BaseModel):
    prompt: str
    options: list[LevelOption] = Field(min_length=2)


class PointARules(RootModel[dict[str, LevelQuestion]]):
    pass


@lru_cache(maxsize=1)
def load_point_a_rules() -> dict[str, LevelQuestion]:
    data = yaml.safe_load(_PATH.read_text(encoding="utf-8"))
    rules = PointARules.model_validate(data).root
    missing = set(SPHERE_IDS) - set(rules.keys())
    if missing:
        raise ValueError(f"point_a_rules.yaml: нет вопроса для сфер {sorted(missing)}")
    return rules


def question_for(sphere_id: str) -> LevelQuestion:
    return load_point_a_rules()[sphere_id]


def level_for_answer(sphere_id: str, option_index: int) -> Optional[int]:
    """Уровень по индексу выбранного варианта (None — индекс вне диапазона,
    например пропуск вопроса без выбора)."""
    question = question_for(sphere_id)
    if 0 <= option_index < len(question.options):
        return question.options[option_index].level
    return None
