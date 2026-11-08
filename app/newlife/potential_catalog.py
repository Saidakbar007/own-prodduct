"""
«Потенциал 30/60/90» (NEWLIFE_2_0.md §2.1 п.8, §Этап 3 Онбординг): одна
простая фраза на цель — «через 30/60/90 дней» — честные цифры из
протоколов docs/knowledge/NEWLIFE_KNOWLEDGE_BASE.md, уже посчитанные и
записанные в `content/potential_30_60_90.yaml` на ru/uz. Загрузчик только
читает и кэширует файл — никаких вычислений "от воздуха" здесь нет.

Покрыты только цели сфер body/mind/energy (см. docstring самого YAML) —
у остальных целей просто нет записи, и экран онбординга её не показывает
(не блокирует переход дальше).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel

_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "potential_30_60_90.yaml"


class PotentialText(BaseModel):
    ru: str
    uz: str

    def text(self, lang: str) -> str:
        return self.uz if lang == "uz" else self.ru


class PotentialEntry(BaseModel):
    goal_id: str
    day_30: Optional[PotentialText] = None
    day_60: Optional[PotentialText] = None
    day_90: Optional[PotentialText] = None


@lru_cache(maxsize=1)
def load_potential_catalog() -> dict[str, PotentialEntry]:
    data = yaml.safe_load(_PATH.read_text(encoding="utf-8")) or {}
    goals = data.get("goals") or {}
    out: dict[str, PotentialEntry] = {}
    for goal_id, row in goals.items():
        out[goal_id] = PotentialEntry(
            goal_id=goal_id,
            day_30=PotentialText.model_validate(row["30"]) if "30" in row else None,
            day_60=PotentialText.model_validate(row["60"]) if "60" in row else None,
            day_90=PotentialText.model_validate(row["90"]) if "90" in row else None,
        )
    return out


def potential_for(goal_id: str) -> Optional[PotentialEntry]:
    return load_potential_catalog().get(goal_id)
