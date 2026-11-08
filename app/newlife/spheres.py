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
    color: str  # hex, см. design/tokens.css --sphere-<id> (NEWLIFE_2_0.md §Этап 4)


SPHERES: list[Sphere] = [
    Sphere(id="body", icon="i-sphere-body", color="#ff5a5a"),
    Sphere(id="mind", icon="i-sphere-mind", color="#7c6bff"),
    Sphere(id="character", icon="i-sphere-character", color="#ffd166"),
    Sphere(id="social", icon="i-sphere-social", color="#5b8def"),
    Sphere(id="career", icon="i-sphere-career", color="#3ddc97"),
    Sphere(id="finance", icon="i-sphere-finance", color="#29c7c7"),
    Sphere(id="relationships", icon="i-sphere-relationships", color="#ff6fae"),
    Sphere(id="knowledge", icon="i-sphere-knowledge", color="#c6e26d"),
    Sphere(id="values", icon="i-sphere-values", color="#b06bff"),
    Sphere(id="lifestyle", icon="i-sphere-lifestyle", color="#6fcf6f"),
    Sphere(id="energy", icon="i-sphere-energy", color="#ff9f43"),
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
