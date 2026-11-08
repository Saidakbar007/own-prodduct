"""
Список проверенных бесплатных ресурсов (доп. задача, см. docs/decisions/
DECISIONS.md → «Этап "Доделай" + guide + wger»): языки, программирование,
финграмотность. Каждая ссылка открыта (WebFetch) перед добавлением в
content/spheres/../../resources.yaml — см. app/newlife/resources.yaml.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

_PATH = Path(__file__).parent / "resources.yaml"

# Какая цель показывает какую категорию ресурсов на карточке сезона —
# контент-привязка, не часть схемы целей (как WORKOUT_PROGRAM_GOALS).
RESOURCE_CATEGORY_FOR_GOAL = {
    "foreign_language": "languages",
    "vocabulary": "languages",
    "programming": "programming",
    "financial_literacy": "financial_literacy",
}


class ResourceText(BaseModel):
    ru: str
    uz: str

    def text(self, lang: str) -> str:
        return self.uz if lang == "uz" else self.ru


class Resource(BaseModel):
    title: str
    url: str
    description: ResourceText


@lru_cache(maxsize=1)
def load_resources() -> dict[str, list[Resource]]:
    data = yaml.safe_load(_PATH.read_text(encoding="utf-8")) or {}
    return {category: [Resource.model_validate(r) for r in items] for category, items in data.items()}


def resources_for_goal(goal_id: str, lang: str) -> list[dict]:
    category = RESOURCE_CATEGORY_FOR_GOAL.get(goal_id)
    if not category:
        return []
    return [
        {"title": r.title, "url": r.url, "description": r.description.text(lang)}
        for r in load_resources().get(category, [])
    ]
