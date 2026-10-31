"""
Загрузка и валидация каталогов привычек (§10 NEWLIFE_V8_SPEC.md):
habit_catalog.yaml (~40 полезных) и bad_habit_catalog.yaml (плохие +
общий список триггеров).
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field

from app.newlife.spheres import SPHERE_BY_ID

_HABIT_PATH = Path(__file__).parent / "habit_catalog.yaml"
_BAD_HABIT_PATH = Path(__file__).parent / "bad_habit_catalog.yaml"


class HabitCatalogItem(BaseModel):
    id: str
    title: str
    spheres: list[str] = Field(min_length=1)
    duration_min: int = Field(gt=0)
    time_pref: Literal["morning", "day", "evening", "exact"]
    minimal: str


class Trigger(BaseModel):
    id: str
    label: str


class BadHabitCatalogItem(BaseModel):
    id: str
    title: str
    unit: Literal["times", "minutes"]
    triggers: list[str] = Field(min_length=1)
    replacement_id: Optional[str] = None


@lru_cache(maxsize=1)
def load_habit_catalog() -> list[HabitCatalogItem]:
    data = yaml.safe_load(_HABIT_PATH.read_text(encoding="utf-8"))
    items = [HabitCatalogItem.model_validate(row) for row in data]
    for item in items:
        unknown = [s for s in item.spheres if s not in SPHERE_BY_ID]
        if unknown:
            raise ValueError(f"habit_catalog.yaml: {item.id} ссылается на неизвестные сферы {unknown}")
    return items


@lru_cache(maxsize=1)
def load_bad_habit_catalog() -> tuple[list[Trigger], list[BadHabitCatalogItem]]:
    data = yaml.safe_load(_BAD_HABIT_PATH.read_text(encoding="utf-8"))
    triggers = [Trigger.model_validate(row) for row in data["triggers"]]
    trigger_ids = {t.id for t in triggers}
    bad_habits = [BadHabitCatalogItem.model_validate(row) for row in data["bad_habits"]]
    for bh in bad_habits:
        unknown = [t for t in bh.triggers if t not in trigger_ids]
        if unknown:
            raise ValueError(f"bad_habit_catalog.yaml: {bh.id} ссылается на неизвестные триггеры {unknown}")
    return triggers, bad_habits


def habit_item_by_id(catalog_id: str) -> Optional[HabitCatalogItem]:
    return next((i for i in load_habit_catalog() if i.id == catalog_id), None)


def bad_habit_item_by_id(catalog_id: str) -> Optional[BadHabitCatalogItem]:
    _, items = load_bad_habit_catalog()
    return next((i for i in items if i.id == catalog_id), None)


def trigger_label(trigger_id: str) -> str:
    triggers, _ = load_bad_habit_catalog()
    match = next((t for t in triggers if t.id == trigger_id), None)
    return match.label if match else trigger_id
