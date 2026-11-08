"""
Банк вопросов для начала разговора (доп. задача, см. docs/decisions/
DECISIONS.md → «Этап "Доделай" + guide + wger») — упомянут в guide цели
start_conversations. Просто список фраз для просмотра (не квиз с ответами),
схема и загрузчик по образцу остальных небольших YAML-банков.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

_PATH = Path(__file__).parent / "conversation_starters.yaml"


class ConversationStarter(BaseModel):
    ru: str
    uz: str

    def text(self, lang: str) -> str:
        return self.uz if lang == "uz" else self.ru


@lru_cache(maxsize=1)
def load_conversation_starters() -> list[ConversationStarter]:
    data = yaml.safe_load(_PATH.read_text(encoding="utf-8"))
    questions = [ConversationStarter.model_validate(q) for q in data["questions"]]
    if len(questions) < 30:
        raise ValueError(f"conversation_starters.yaml: ожидалось минимум 30 вопросов, нашлось {len(questions)}")
    return questions


def conversation_starters_for_display(lang: str) -> list[str]:
    return [q.text(lang) for q in load_conversation_starters()]
