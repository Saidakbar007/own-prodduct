"""
Витринные описания библиотечных шаблонов для каталога «Сезоны» (сложность,
для кого, что будет в конце). Чисто текст для карточек — не часть
engine-схемы шаблона (§5 ТЗ), поэтому живёт отдельно от YAML.
"""

import zlib

CATALOG_META: dict[str, dict[str, str]] = {
    "run_5k": {
        "difficulty": "Для новичков",
        "for_whom": "Для тех, кто пока не пробегает и пяти минут без остановки",
        "outcome": "В конце — 5 км бега без остановки",
    },
    "pullups_10": {
        "difficulty": "Средний уровень",
        "for_whom": "Для тех, кто пока не может подтянуться ни разу",
        "outcome": "В конце — 10 чистых подтягиваний подряд",
    },
    "pushups_50": {
        "difficulty": "Для новичков",
        "for_whom": "Для тех, кто хочет укрепить верх тела без зала",
        "outcome": "В конце — 50 отжиманий подряд",
    },
    "fat_loss_safe": {
        "difficulty": "Средний уровень",
        "for_whom": "Для тех, кто хочет снижать вес безопасно, без жёстких диет",
        "outcome": "В конце — снижение веса в безопасном темпе и новые привычки",
    },
    "muscle_gain": {
        "difficulty": "Для продолжающих",
        "for_whom": "Для тех, кто хочет растить силу и мышцы с нуля в зале",
        "outcome": "В конце — заметно больший рабочий вес и рост массы тела",
    },
}

DEFAULT_META = {
    "difficulty": "Свой уровень",
    "for_whom": "Под твою собственную цель",
    "outcome": "Результат — по условиям, которые задаёт сама цель",
}


def meta_for(template_id: str) -> dict[str, str]:
    return CATALOG_META.get(template_id, DEFAULT_META)


HERO_STAGE_COUNT = 5
_POSTER_HERO: dict[str, int] = {
    "run_5k": 1,
    "pullups_10": 2,
    "pushups_50": 3,
    "fat_loss_safe": 4,
    "muscle_gain": 5,
}


def poster_hero_for(template_id: str) -> int:
    """Какой кадр 3D-арта героя (1..5) показывать на постере шаблона —
    фиксированный для пяти библиотечных, стабильный хэш для остальных (своя
    цель от ИИ), чтобы постер не прыгал между перезагрузками."""
    if template_id in _POSTER_HERO:
        return _POSTER_HERO[template_id]
    # zlib.crc32, не built-in hash(): hash() рандомизирован PYTHONHASHSEED
    # на каждый процесс — постер бы "прыгал" между перезапусками сервиса.
    return (zlib.crc32(template_id.encode("utf-8")) % HERO_STAGE_COUNT) + 1
