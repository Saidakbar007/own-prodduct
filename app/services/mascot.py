"""
Ведущий (§8 ТЗ): банк реплик по событиям (app/i18n/mascot.json) + состояние
для анимации (рад/спокоен/волнуется/спит). Рабочее имя и арт — заглушка,
заменяется без правки этой логики.
"""

import json
import random
from pathlib import Path
from typing import Literal

MascotState = Literal["glad", "calm", "worried", "asleep"]

_PATH = Path(__file__).parent.parent / "i18n" / "mascot.json"
_CACHE: dict | None = None

EVENT_STATE: dict[str, MascotState] = {
    "trailer": "glad",
    "wave_start": "glad",
    "pending": "calm",
    "done": "glad",
    "minimal": "calm",
    "skip": "worried",
    "second_chance_used": "calm",
    "chances_exhausted": "worried",
    "measure_better": "glad",
    "measure_worse": "calm",
    "episode_exit": "glad",
    "week_before_final": "calm",
    "reveal_clean": "glad",
    "reveal_passed": "glad",
    "reveal_completed": "calm",
    "next_season": "glad",
}


def _load() -> dict:
    global _CACHE
    if _CACHE is None:
        _CACHE = json.loads(_PATH.read_text(encoding="utf-8"))
    return _CACHE


def phrase_for(event: str, lang: str = "ru") -> str:
    """Случайная реплика ведущего для события на нужном языке (откат на ru)."""
    data = _load()
    variants = data.get(lang, {}).get(event) or data.get("ru", {}).get(event)
    if not variants:
        return ""
    return random.choice(variants)


def state_for(event: str) -> MascotState:
    """Состояние для анимации, соответствующее событию (по умолчанию — calm)."""
    return EVENT_STATE.get(event, "calm")
