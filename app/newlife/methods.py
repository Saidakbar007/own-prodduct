"""
Методы саморазвития как правила (§9 NEWLIFE_V8_SPEC.md) — чистые функции
определения триггеров + каталог для страницы «Методы NewLife». Тексты
пересказаны своими словами, с подписью «по мотивам …» (см. i18n methods.*).

Часть методов уже вшита в другие модули, а не как отдельное срабатывание:
- intention_if_then (Gollwitzer) — поле Habit.if_then_text при создании.
- woop (Oettingen) — экран /onboarding/woop.
- two_minute_rule (Clear) — Habit.minimal_version обязателен всегда.
- load_progression (ACSM) — app/routers/measure.py (adapt_phase).
Здесь — только триггеры, для которых нужна отдельная детектирующая логика.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

RECOVERY_MODE_DAYS = 7
RECOVERY_MISS_THRESHOLD = 3  # §9: 3+ пропуска за 7 дней
RECOVERY_LOW_ENERGY_THRESHOLD = 2
RECOVERY_LOW_ENERGY_STREAK = 3  # энергия <= 2 три дня подряд
STRESS_TALK_THRESHOLD = 4
STRESS_TALK_STREAK_DAYS = 7  # §11: мягкий совет при стрессе >=4 семь дней подряд
SLEEP_HYGIENE_WINDOW_MIN = 60  # §9: за 60 минут до отбоя


@dataclass(frozen=True)
class Method:
    id: str
    name: str
    trigger: str
    source: str


METHODS: list[Method] = [
    Method("intention_if_then", "Намерение «если — то»", "Создание привычки", "Gollwitzer"),
    Method("woop", "WOOP", "Онбординг, новая цель", "Oettingen"),
    Method("anchor_habit", "Привычка-якорь", "Привычка пропущена 2+ раз из-за «забыл»", "Clear, Fogg"),
    Method("two_minute_rule", "Правило двух минут", "Любая привычка — минимальная версия всегда есть", "Clear"),
    Method("dont_skip_twice", "Не пропускай дважды", "Один пропуск", "Clear"),
    Method("identity_shift", "Идентичность", "Итог недели", "Clear"),
    Method("environment_design", "Дизайн окружения", "Вечер перед тренировкой/учёбой", "Clear"),
    Method("temptation_bundling", "Связка удовольствия", "Отметка «скучно» в причинах пропуска", "Milkman"),
    Method("eisenhower_matrix", "Матрица Эйзенхауэра", "Создание задачи", "Эйзенхауэр"),
    Method("load_progression", "Прогрессия нагрузки", "Силовые — результат выше ожидаемого", "ACSM"),
    Method("sleep_hygiene", "Гигиена сна", "За 60 минут до отбоя", "AASM"),
    Method("recovery_mode", "Режим восстановления", "3+ пропуска за 7 дней или энергия ≤ 2 три дня подряд", "—"),
]

METHOD_BY_ID: dict[str, Method] = {m.id: m for m in METHODS}


def should_suggest_recovery_mode(
    missed_count_last_7_days: int, energy_last_3_days: list[int]
) -> bool:
    """§9/§11: 3+ пропуска за неделю ИЛИ энергия <=2 три дня подряд."""
    if missed_count_last_7_days >= RECOVERY_MISS_THRESHOLD:
        return True
    if len(energy_last_3_days) >= RECOVERY_LOW_ENERGY_STREAK and all(
        e <= RECOVERY_LOW_ENERGY_THRESHOLD for e in energy_last_3_days[-RECOVERY_LOW_ENERGY_STREAK:]
    ):
        return True
    return False


def should_suggest_anchor(consecutive_forgot_misses: int, main_obstacle: str | None) -> bool:
    """§9 Clear/Fogg: привычка пропущена 2+ раз из-за «забыл»."""
    return main_obstacle == "forget" and consecutive_forgot_misses >= 2


def should_show_dont_skip_twice_nudge(yesterday_status: str | None) -> bool:
    """§9 Clear: один пропуск — на завтра мягкая подсказка и минимум."""
    return yesterday_status in ("missed", None)


def should_suggest_stress_talk(stress_values_last_7_days: list[int]) -> bool:
    """§11: стресс >= 4 семь дней подряд — мягкий совет поговорить с кем-то.
    Не диагностика."""
    if len(stress_values_last_7_days) < STRESS_TALK_STREAK_DAYS:
        return False
    return all(s >= STRESS_TALK_THRESHOLD for s in stress_values_last_7_days[-STRESS_TALK_STREAK_DAYS:])


def should_show_sleep_hygiene_reminder(now_minutes: int, sleep_time_minutes: int) -> bool:
    """§9 AASM: подсказка «без экрана» в окне [sleep-60, sleep) минут."""
    window_start = sleep_time_minutes - SLEEP_HYGIENE_WINDOW_MIN
    return window_start <= now_minutes < sleep_time_minutes


def should_suggest_temptation_bundling(recent_trigger_ids: list[str]) -> bool:
    """§9 Milkman: отметка «скучно» (boredom) среди причин пропуска/срыва."""
    return "boredom" in recent_trigger_ids


def is_recovery_mode_active(started_on: date, today: date, accepted: bool) -> bool:
    return accepted and started_on <= today < started_on + timedelta(days=RECOVERY_MODE_DAYS)
