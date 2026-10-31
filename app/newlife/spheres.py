"""
11 сфер жизни (§3 NEWLIFE_V8_SPEC.md). Названия/описания — в i18n
(`sphere.<id>.name`, `sphere.<id>.description`), здесь только константы и
порядок показа. В v8 полностью работает каталог целей только для "body" —
остальные сферы видны в онбординге и колесе жизни с пометкой "скоро".
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

# §3: "в v8 полностью работают: сфера Тело... каталоги целей остальных сфер —
# пометка «скоро»". Привычки/плохие привычки можно заводить в любую сферу уже
# сейчас — ограничение только на каталог ЦЕЛЕЙ (Goal/сезоны).
SPHERES_WITH_GOAL_CATALOG: set[str] = {"body"}


def is_valid_sphere(sphere_id: str) -> bool:
    return sphere_id in SPHERE_BY_ID


def has_goal_catalog(sphere_id: str) -> bool:
    return sphere_id in SPHERES_WITH_GOAL_CATALOG
