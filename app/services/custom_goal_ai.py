"""
ИИ-генерация шаблона сезона под "свою цель" (§5 ТЗ, Фаза 4). Один запрос к
модели на цель (плюс одна повторная попытка при невалидном ответе), строгая
валидация той же pydantic-схемой, что и библиотечные шаблоны (§6: те же
ограничения безопасности действуют и на сгенерированные шаблоны). Результат
кэшируется как draft (БД) и переиспользуется для похожих целей; админ может
утвердить черновик — тогда он доступен наравне с библиотечными.

Вызывается из app.services.custom_goal.generate_custom_template только если
задан ANTHROPIC_API_KEY — без ключа эта функция не импортируется.
"""

import hashlib
import json
import re
from typing import Optional

import yaml
from pydantic import ValidationError
from sqlmodel import Session, select

from app.models import CustomTemplateDraft
from app.seasons.schema import SeasonTemplate
from app.seasons_library.loader import register_custom_template

MODEL = "claude-sonnet-5"
MAX_TOKENS = 4000

SYSTEM_PROMPT = """Ты — осторожный тренер, который составляет безопасный персональный \
план-сезон по шаблону ниже. Отвечай ТОЛЬКО одним YAML-документом в тройных \
бэктиках (```yaml ... ```), без пояснений до или после. Строго соблюдай эту структуру:

id: короткий_английский_идентификатор_без_пробелов
version: 1
title: "Название по-русски"
title_uz: "Название на узбекской латинице"
category: fitness
metric: {name: "Название метрики", unit: "единица", direction: up|down}
lengths: [30, 60, 90]   # подходящие длины сезона из этого набора
target_default: число   # ожидаемое изменение метрики от baseline к финалу
baseline_test:
  prompt: "Вопрос для определения стартового уровня"
  input: number
  min: число
  max: число
eligibility:
  min_age: 18
  warnings: ["текст предупреждения, если уместно"]
schedule: {train_days: [1,3,5], minutes: [20, 40]}   # 1=пн..7=вс
phases:
  - phase: 1
    unlock_if_baseline_gte: 0
    days:
      - title: "Название дня"
        instructions: "Подробная инструкция"
        minimal: "Облегчённый вариант"
        expected_progress: число больше 0
  # 2-5 фаз с растущими порогами unlock_if_baseline_gte
rest_day: {title: "День восстановления", instructions: "..."}
measure_every_days: 7
measure: {prompt: "Вопрос замера", proof: optional, progress_photo: false}
safety: {max_phase_jump: 1, rest_days_min_per_week: 1}

Жёсткие правила безопасности: минимум 1 день отдыха в неделю, никаких \
экстремальных нагрузок, при похудении/наборе веса метрика — изменение \
веса тела, а не абсолютное значение. Если цель пользователя потенциально \
опасна или не про физическую активность/здоровье — всё равно верни валидный \
YAML с мягким и безопасным планом, approximating её как можно честнее."""


def _cache_key(goal_text: str) -> str:
    return hashlib.sha256(goal_text.strip().lower().encode("utf-8")).hexdigest()


def _extract_yaml(text: str) -> str:
    match = re.search(r"```(?:yaml)?\s*(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def call_model(goal_text: str) -> str:
    """Один запрос к модели. Вынесено отдельно, чтобы тесты могли подменить
    эту функцию, не трогая реальный API."""
    from anthropic import Anthropic

    client = Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Цель пользователя: {goal_text}"}],
    )
    return "".join(block.text for block in response.content if hasattr(block, "text"))


def parse_and_validate(raw_text: str, goal_text: str) -> Optional[SeasonTemplate]:
    try:
        yaml_text = _extract_yaml(raw_text)
        data = yaml.safe_load(yaml_text)
        if not isinstance(data, dict):
            return None
        data["id"] = f"custom_{_cache_key(goal_text)[:12]}"
        return SeasonTemplate.model_validate(data)
    except (yaml.YAMLError, ValidationError, TypeError, KeyError):
        return None


def generate_with_ai(db: Session, goal_text: str) -> Optional[SeasonTemplate]:
    """Главная точка входа: кэш -> (до двух попыток генерации) -> сохранение
    драфта в БД. Возвращает None при честном отказе (невалидный ответ дважды)."""
    key = _cache_key(goal_text)

    cached = db.exec(
        select(CustomTemplateDraft).where(CustomTemplateDraft.goal_text_hash == key)
    ).first()
    if cached:
        try:
            template = SeasonTemplate.model_validate(yaml.safe_load(cached.template_yaml))
            register_custom_template(template)
            return template
        except (yaml.YAMLError, ValidationError):
            pass  # кэш повреждён — сгенерируем заново

    template = None
    for _attempt in range(2):
        try:
            raw = call_model(goal_text)
        except Exception:
            continue
        template = parse_and_validate(raw, goal_text)
        if template:
            break

    if not template:
        return None

    draft = CustomTemplateDraft(
        goal_text=goal_text,
        goal_text_hash=key,
        template_id=template.id,
        template_yaml=yaml.safe_dump(json.loads(template.model_dump_json()), allow_unicode=True),
    )
    db.add(draft)
    db.commit()
    register_custom_template(template)
    return template
