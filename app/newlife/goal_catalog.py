"""
Каталог целей сферы (PRD 1.0 "11 сфер: каталог контента") — один YAML на
сферу в `content/spheres/<sphere>.yaml`, схема на pydantic, загрузчик с
кэшем. Заменяет `app/seasons_library/catalog_meta.py` (витринный текст для
карточек целей, раньше жил отдельно от YAML — см. его старый docstring).

Что НЕ входит сюда (сознательно, см. docs/decisions/DECISIONS.md → «NewLife
1.0»): привычки/вредные привычки — общий `app/newlife/habit_catalog.yaml` /
`bad_habit_catalog.yaml` (уже помечены полем `spheres`, одна привычка может
относиться к нескольким сферам), вопрос точки А — `point_a_rules.yaml`,
банк "вопрос дня" — отдельный файл (ещё не создан, Этап 2 п.7 START_1.0.md).
Здесь — только каталог ЦЕЛЕЙ: метрика, варианты цели, темп, источник.

Сценарий сезона (день за днём, фазы прогрессии) для цели, у которой он есть,
остаётся в `app/seasons_library/<goal_id>.yaml` (SeasonTemplate) — это и есть
реализация `week_skeleton`/`minimal_version` для целей с прогрессией
(тренировки). Для простых целей-счётчиков week_skeleton/minimal_version —
просто текст, но Season/Goal всё равно создаётся по тому же шаблону (там
всегда ровно один шаблон на цель — простой однофазный, как sleep_consistency).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, model_validator

_CONTENT_DIR = Path(__file__).resolve().parent.parent.parent / "content" / "spheres"

MetricKind = Literal["measure", "counter", "timer", "boolean", "percent"]


class GoalTitle(BaseModel):
    ru: str
    uz: str


class GoalMetric(BaseModel):
    key: str  # семантический id метрики: weight_body | run_minutes | max_reps | ...
    kind: MetricKind
    unit: str
    rounding: float = Field(gt=0)  # шаг округления (app.newlife.rounding.round_to_step)


class GoalSource(BaseModel):
    name: str
    url: Optional[str] = None

    @property
    def is_heuristic(self) -> bool:
        return self.url is None


class GoalCatalogEntry(BaseModel):
    id: str
    sphere: str
    title: GoalTitle
    difficulty: str
    for_whom: str
    outcome: str
    metric: GoalMetric
    secondary: list[str] = Field(default_factory=list)
    # PRD: "2-3 варианта кнопками" — норма; 1 допускается, если у цели
    # реально есть только один вариант (например muscle_gain: lengths=[90]).
    targets: list[str] = Field(min_length=1, max_length=3)
    pace: str
    week_skeleton: str
    minimal_version: str
    source: GoalSource
    # Шаблон сезона (день за днём) из app/seasons_library/, если у цели есть
    # сценарий прогрессии; без него цель можно показать в каталоге, но пока
    # нельзя начать как Season (см. docstring модуля).
    template_id: Optional[str] = None


class SphereCatalog(BaseModel):
    sphere: str
    goals: list[GoalCatalogEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_goals_belong_to_sphere(self) -> "SphereCatalog":
        for goal in self.goals:
            if goal.sphere != self.sphere:
                raise ValueError(
                    f"цель '{goal.id}' помечена sphere='{goal.sphere}', "
                    f"а файл — для сферы '{self.sphere}'"
                )
        ids = [g.id for g in self.goals]
        if len(set(ids)) != len(ids):
            raise ValueError(f"повторяющийся id цели в каталоге '{self.sphere}'")
        return self


def catalog_files() -> list[Path]:
    """Все YAML-каталоги сфер, отсортированные по имени."""
    return sorted(_CONTENT_DIR.glob("*.yaml"))


def load_catalog(path: Path) -> SphereCatalog:
    """Загружает и валидирует один файл каталога сферы."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    catalog = SphereCatalog.model_validate(data)
    if catalog.sphere != path.stem:
        raise ValueError(f"{path.name}: sphere '{catalog.sphere}' не совпадает с именем файла")
    return catalog


@lru_cache(maxsize=1)
def load_all_catalogs() -> dict[str, SphereCatalog]:
    """Все каталоги сфер, ключ — id сферы."""
    catalogs: dict[str, SphereCatalog] = {}
    for path in catalog_files():
        catalog = load_catalog(path)
        if catalog.sphere in catalogs:
            raise ValueError(f"Повторяющийся каталог сферы: {catalog.sphere}")
        catalogs[catalog.sphere] = catalog
    return catalogs


def available_sphere_ids() -> set[str]:
    """Сферы, у которых уже есть каталог целей — заменяет старую константу
    SPHERES_WITH_GOAL_CATALOG (app/newlife/spheres.py)."""
    return set(load_all_catalogs().keys())


def goals_for_sphere(sphere_id: str) -> list[GoalCatalogEntry]:
    catalog = load_all_catalogs().get(sphere_id)
    return catalog.goals if catalog else []


def all_goals() -> list[GoalCatalogEntry]:
    """Цели всех сфер подряд — для страницы «Откуда эти нормы» и т.п."""
    goals: list[GoalCatalogEntry] = []
    for catalog in load_all_catalogs().values():
        goals.extend(catalog.goals)
    return goals


def goal_meta(goal_id: str) -> Optional[GoalCatalogEntry]:
    """Одна цель по id, независимо от сферы; None, если не найдена."""
    for goal in all_goals():
        if goal.id == goal_id:
            return goal
    return None
