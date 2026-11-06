"""
11 сфер жизни (§3 docs/specs/NEWLIFE_V8_SPEC.md). Названия/описания — в i18n
(`sphere.<id>.name`, `sphere.<id>.description`), здесь только константы и
порядок показа. Каталог целей (есть ли у сферы цели, которые можно выбрать
в онбординге) — не хардкод, а то, что реально загрузилось из
content/spheres/*.yaml (PRD 1.0 F2, см. app/newlife/goal_catalog.py). Пока
каталог готов только для "body" — остальные сферы видны в онбординге и
колесе жизни с пометкой "скоро", и появятся сами по себе, когда для них
добавят YAML-каталог — без изменений в этом модуле.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Sphere:
    id: str
    icon: str  # id символа в SVG-спрайте (<use href="#{icon}"/>)


SPHERES: list[Sphere] = [
    Sphere(id="body", icon="i-sphere-body"),
    Sphere(id="mind", icon="i-sphere-mind"),
    Sphere(id="character", icon="i-sphere-character"),
    Sphere(id="social", icon="i-sphere-social"),
    Sphere(id="career", icon="i-sphere-career"),
    Sphere(id="finance", icon="i-sphere-finance"),
    Sphere(id="relationships", icon="i-sphere-relationships"),
    Sphere(id="knowledge", icon="i-sphere-knowledge"),
    Sphere(id="values", icon="i-sphere-values"),
    Sphere(id="lifestyle", icon="i-sphere-lifestyle"),
    Sphere(id="energy", icon="i-sphere-energy"),
]

SPHERE_IDS: list[str] = [s.id for s in SPHERES]
SPHERE_BY_ID: dict[str, Sphere] = {s.id: s for s in SPHERES}

def is_valid_sphere(sphere_id: str) -> bool:
    return sphere_id in SPHERE_BY_ID


def has_goal_catalog(sphere_id: str) -> bool:
    """Привычки/плохие привычки можно заводить в любую сферу уже сейчас —
    ограничение только на каталог ЦЕЛЕЙ (Goal/сезоны): пока для сферы нет
    content/spheres/<id>.yaml, она видна в онбординге/колесе с пометкой
    "скоро"."""
    from app.newlife.goal_catalog import available_sphere_ids

    return sphere_id in available_sphere_ids()
