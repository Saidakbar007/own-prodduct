"""
Какой кадр 3D-арта героя показывать на постере шаблона сезона — чисто
визуальный выбор, не часть каталога целей (витринный текст карточек и
правильные метрики — перенесены в content/spheres/body.yaml, см.
app/newlife/goal_catalog.py и docs/decisions/DECISIONS.md → «NewLife 1.0»).
"""

import zlib

HERO_STAGE_COUNT = 5
_POSTER_HERO: dict[str, int] = {
    "run_5k": 1,
    "pullups_10": 2,
    "pushups_50": 3,
    "fat_loss_safe": 4,
    "muscle_gain": 5,
    "activity_steps": 2,
    "sleep_consistency": 4,
}


def poster_hero_for(template_id: str) -> int:
    """Какой кадр 3D-арта героя (1..5) показывать на постере шаблона —
    фиксированный для библиотечных, стабильный хэш для остальных (своя
    цель от ИИ), чтобы постер не прыгал между перезагрузками."""
    if template_id in _POSTER_HERO:
        return _POSTER_HERO[template_id]
    # zlib.crc32, не built-in hash(): hash() рандомизирован PYTHONHASHSEED
    # на каждый процесс — постер бы "прыгал" между перезапусками сервиса.
    return (zlib.crc32(template_id.encode("utf-8")) % HERO_STAGE_COUNT) + 1
