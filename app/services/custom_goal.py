"""
"Своя цель" (§5 ТЗ): поиск по библиотеке — ИИ-генерация подключена в Фазе 4
(нужен ANTHROPIC_API_KEY, иначе честное "скоро появится").
"""

import os
from typing import Optional

from sqlmodel import Session

from app.seasons.schema import SeasonTemplate


def ai_generation_available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def generate_custom_template(db: Session, goal_text: str) -> Optional[SeasonTemplate]:
    """Без ключа — всегда None (честное "скоро появится"). С ключом —
    кэшированная ИИ-генерация с валидацией по той же схеме, что и
    библиотечные шаблоны (app/services/custom_goal_ai.py)."""
    if not ai_generation_available():
        return None
    from app.services.custom_goal_ai import generate_with_ai

    return generate_with_ai(db, goal_text)
