"""
"Своя цель" (§5 ТЗ): поиск по библиотеке — ИИ-генерация описана отдельно для
Фазы 4 (нужен ANTHROPIC_API_KEY). Здесь — только интерфейс, которым
пользуется онбординг Фазы 2; тело функции заполнится в Фазе 4, сам роут
менять не придётся.
"""

import os
from typing import Optional

from app.seasons.schema import SeasonTemplate


def ai_generation_available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def generate_custom_template(goal_text: str) -> Optional[SeasonTemplate]:
    """Фаза 2: всегда None (честное "скоро появится"). Фаза 4 добавит
    настоящий запрос к модели + кэш + валидацию, без изменения вызывающего
    кода в app/routers/onboarding.py."""
    if not ai_generation_available():
        return None
    from app.services.custom_goal_ai import generate_with_ai  # импорт здесь — Фаза 4

    return generate_with_ai(goal_text)
