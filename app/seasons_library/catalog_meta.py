"""
Витринные описания библиотечных шаблонов для каталога «Цели» (сложность,
для кого, что будет в конце — UX-правка) и правильные метрики по сфере
«Тело» (§7 NEWLIFE_V8_SPEC.md: главная метрика, вспомогательные, безопасные
рамки, источник). Чисто текст для карточек — не часть engine-схемы шаблона
(§5 ТЗ Сезонов), поэтому живёт отдельно от YAML.
"""

import zlib

CATALOG_META: dict[str, dict] = {
    "run_5k": {
        "difficulty": "Для новичков",
        "for_whom": "Для тех, кто пока не пробегает и пяти минут без остановки",
        "outcome": "В конце — 5 км бега без остановки",
        "metric_key": "run_minutes",
        "secondary": ["пробежек в неделю"],
        "safe_rate": "9 недель, 3 пробежки в неделю, день отдыха между ними",
        "source": "NHS Couch to 5K",
        "source_url": "https://www.nhs.uk/better-health/get-active/get-running-with-couch-to-5k/couch-to-5k-running-plan/",
    },
    "pullups_10": {
        "difficulty": "Средний уровень",
        "for_whom": "Для тех, кто пока не может подтянуться ни разу",
        "outcome": "В конце — 10 чистых подтягиваний подряд",
        "metric_key": "max_reps",
        "secondary": ["недельный объём"],
        "safe_rate": "2–3 тренировки в неделю; прогрессия при +1–2 повторениях сверх цели",
        "source": "ACSM Position Stand",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/19204579/",
    },
    "pushups_50": {
        "difficulty": "Для новичков",
        "for_whom": "Для тех, кто хочет укрепить верх тела без зала",
        "outcome": "В конце — 50 отжиманий подряд",
        "metric_key": "max_reps",
        "secondary": ["недельный объём"],
        "safe_rate": "2–3 тренировки в неделю; прогрессия при +1–2 повторениях сверх цели",
        "source": "ACSM Position Stand",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/19204579/",
    },
    "fat_loss_safe": {
        "difficulty": "Средний уровень",
        "for_whom": "Для тех, кто хочет снижать вес безопасно, без жёстких диет",
        "outcome": "В конце — снижение веса в безопасном темпе и новые привычки",
        "metric_key": "weight_body",
        "secondary": ["обхват талии", "шаги", "силовые 2×/нед"],
        "safe_rate": "−0,5–1 кг в неделю (не быстрее 1% массы тела); при ИМТ < 18,5 недоступно",
        "source": "CDC / WHO",
        "source_url": "https://webharvest.gov/congress115th/20181203203029/https://www.cdc.gov/healthyweight/losing_weight/index.html",
    },
    "muscle_gain": {
        "difficulty": "Для продолжающих",
        "for_whom": "Для тех, кто хочет растить силу и мышцы с нуля в зале",
        "outcome": "В конце — заметно больший рабочий вес и рост массы тела",
        "metric_key": "weight_body",
        "secondary": ["обхваты (талия, грудь, плечо, бедро)", "фото раз в 2 недели", "рабочие веса — индикатор тренировки"],
        "safe_rate": "+0,25–0,5% веса тела в неделю; белок 1,4–2,0 г/кг/сут; силовые 2–3 раза в неделю",
        "source": "Iraki 2019 / ISSN / ACSM",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC6680710/",
    },
    "activity_steps": {
        "difficulty": "Для новичков",
        "for_whom": "Для тех, кто хочет больше двигаться в течение дня",
        "outcome": "В конце — уверенные 8–10 тыс. шагов в день",
        "metric_key": "steps_avg7d",
        "secondary": ["минуты активности"],
        "safe_rate": "рост постепенно, +500–1000 шагов в неделю; 150–300 мин/нед активности",
        "source": "Paluch 2022 / WHO",
        "source_url": "https://www.eurekalert.org/news-releases/945267",
    },
    "sleep_consistency": {
        "difficulty": "Для новичков",
        "for_whom": "Для тех, кто хочет высыпаться и ложиться/вставать стабильно",
        "outcome": "В конце — 7+ часов сна и стабильный режим",
        "metric_key": "sleep_hours_avg7d",
        "secondary": ["разброс времени подъёма"],
        "safe_rate": "7+ часов; подъём ± 30 минут изо дня в день",
        "source": "AASM / SRS",
        "source_url": "https://aasm.org/aasm-and-srs-publish-new-sleep-duration-consensus-statement/",
    },
}

DEFAULT_META = {
    "difficulty": "Свой уровень",
    "for_whom": "Под твою собственную цель",
    "outcome": "Результат — по условиям, которые задаёт сама цель",
    "metric_key": "custom",
    "secondary": [],
    "safe_rate": "",
    "source": "",
    "source_url": "",
}


def meta_for(template_id: str) -> dict:
    return CATALOG_META.get(template_id, DEFAULT_META)


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
