"""
Планировщик дня/недели (§6 docs/specs/NEWLIFE_V8_SPEC.md) — детерминированный алгоритм,
чистые функции (не трогают БД и часы). Входы — простые значения (минуты от
полуночи), выходы — простые значения, поэтому полностью покрывается
юнит-тестами таблицами случаев (tests/test_scheduler.py).

Шаги (§6):
1. Неподвижные блоки: сон, обязательные дела, дорога, задачи с временем.
2. Свободные окна >= MIN_WINDOW_MINUTES.
3. Расставить: действия сезонов -> привычки -> задачи без времени
   (по приоритету Эйзенхауэра и дедлайну).
4. Энергия: тяжёлое — в окна, совпадающие с chronotype; лёгкое — в остальные.
5. Лимиты: не больше daily_minutes на развитие; запас 15% свободного времени;
   минимум 1 день отдыха от тренировок в неделю; сон не трогаем никогда.
6. Конфликт/нехватка места -> минимальная версия -> перенос на ближайший
   день -> сообщение одной строкой.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

MIN_WINDOW_MINUTES = 10
DEFAULT_BUFFER_RATIO = 0.15  # §6 п.5: запас 15% свободного времени

# §6 п.4: приблизительные окна бодрости по хронотипу (минуты от полуночи).
# "varies" — предпочтения нет, тяжёлое просто идёт в первое окно по порядку.
CHRONOTYPE_WINDOWS: dict[str, tuple[int, int]] = {
    "morning": (6 * 60, 11 * 60),
    "day": (11 * 60, 17 * 60),
    "evening": (17 * 60, 22 * 60),
}

EISENHOWER_ORDER = {"do": 0, "plan": 1, "delegate": 2, "drop": 3}

BlockKind = Literal["fixed", "sleep", "goal_action", "habit", "task"]


@dataclass(frozen=True)
class FixedBlock:
    """Неподвижный интервал дня — сон, обязательное дело, дорога, задача с
    фиксированным временем. Планировщик никогда их не трогает."""

    start_min: int
    end_min: int
    kind: str  # "sleep" | "commitment" | "task_fixed"
    title: str
    ref_type: Optional[str] = None
    ref_id: Optional[int] = None


@dataclass(frozen=True)
class Candidate:
    """Что нужно расставить сегодня: действие дня сезона, привычка или
    задача без фиксированного времени."""

    kind: Literal["goal_action", "habit", "task"]
    title: str
    duration_min: int
    ref_type: str
    ref_id: int
    heavy: bool = False  # тренировка/учёба >= 30 мин — в окно по хронотипу
    eisenhower: Optional[str] = None  # только для task: do|plan|delegate|drop
    deadline_days: Optional[int] = None  # дней до дедлайна (для сортировки задач)
    minimal_duration_min: Optional[int] = None  # None — минимальной версии нет


@dataclass(frozen=True)
class PlacedBlock:
    start_min: int
    end_min: int
    kind: str
    title: str
    ref_type: Optional[str]
    ref_id: Optional[int]
    is_minimal: bool = False


@dataclass
class DayScheduleResult:
    blocks: list[PlacedBlock] = field(default_factory=list)
    unplaced: list[Candidate] = field(default_factory=list)  # не влезло даже минимально
    messages: list[str] = field(default_factory=list)


def free_windows(
    day_start_min: int, day_end_min: int, fixed_blocks: list[FixedBlock], min_window: int = MIN_WINDOW_MINUTES
) -> list[tuple[int, int]]:
    """Свободные окна >= min_window минут между неподвижными блоками, в
    пределах [day_start_min, day_end_min) (бодрствование — после подъёма, до
    отбоя)."""
    occupied = sorted(
        [(max(b.start_min, day_start_min), min(b.end_min, day_end_min)) for b in fixed_blocks if b.end_min > day_start_min and b.start_min < day_end_min],
        key=lambda x: x[0],
    )
    windows: list[tuple[int, int]] = []
    cursor = day_start_min
    for start, end in occupied:
        if start > cursor:
            windows.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < day_end_min:
        windows.append((cursor, day_end_min))
    return [(s, e) for s, e in windows if e - s >= min_window]


def _overlaps_chronotype(window: tuple[int, int], chronotype: str) -> bool:
    bounds = CHRONOTYPE_WINDOWS.get(chronotype)
    if not bounds:
        return True  # "varies" — любое окно подходит
    w_start, w_end = window
    b_start, b_end = bounds
    return w_start < b_end and w_end > b_start


def _task_sort_key(c: Candidate) -> tuple:
    order = EISENHOWER_ORDER.get(c.eisenhower or "plan", 1)
    deadline = c.deadline_days if c.deadline_days is not None else 9999
    return (order, deadline)


def build_day_schedule(
    fixed_blocks: list[FixedBlock],
    day_start_min: int,
    day_end_min: int,
    goal_actions: list[Candidate],
    habits: list[Candidate],
    tasks: list[Candidate],
    chronotype: str = "varies",
    daily_minutes_limit: int = 60,
    buffer_ratio: float = DEFAULT_BUFFER_RATIO,
) -> DayScheduleResult:
    """Расставляет один день (§6 п.1-6). Порядок расстановки кандидатов:
    действия сезонов -> привычки -> задачи (по Эйзенхауэру и дедлайну)."""
    result = DayScheduleResult()
    windows = free_windows(day_start_min, day_end_min, fixed_blocks)
    total_free = sum(e - s for s, e in windows)
    budget = min(daily_minutes_limit, total_free * (1 - buffer_ratio))

    ordered_tasks = sorted(tasks, key=_task_sort_key)
    candidates = list(goal_actions) + list(habits) + ordered_tasks

    used_minutes = 0.0
    for candidate in candidates:
        duration = candidate.duration_min
        is_minimal = False

        if candidate.kind != "task" and used_minutes + duration > budget:
            # Бюджет на развитие исчерпан — пробуем минимальную версию.
            if candidate.minimal_duration_min is not None and used_minutes + candidate.minimal_duration_min <= budget:
                duration = candidate.minimal_duration_min
                is_minimal = True
            else:
                result.unplaced.append(candidate)
                result.messages.append(f'"{candidate.title}" не влезает сегодня — перенесено на ближайший день')
                continue

        placed = _place_in_windows(windows, duration, candidate.heavy, chronotype)
        if placed is None and candidate.minimal_duration_min is not None and not is_minimal:
            duration = candidate.minimal_duration_min
            is_minimal = True
            placed = _place_in_windows(windows, duration, candidate.heavy, chronotype)

        if placed is None:
            result.unplaced.append(candidate)
            result.messages.append(f'"{candidate.title}" не влезает сегодня — перенесено на ближайший день')
            continue

        start, end = placed
        windows = _consume_window(windows, start, end)
        result.blocks.append(
            PlacedBlock(
                start_min=start,
                end_min=end,
                kind=candidate.kind,
                title=candidate.title,
                ref_type=candidate.ref_type,
                ref_id=candidate.ref_id,
                is_minimal=is_minimal,
            )
        )
        if candidate.kind != "task":
            used_minutes += duration

    result.blocks.sort(key=lambda b: b.start_min)
    return result


def _place_in_windows(
    windows: list[tuple[int, int]], duration: int, heavy: bool, chronotype: str
) -> Optional[tuple[int, int]]:
    """Ищет окно под кандидата: тяжёлое — сперва окно по хронотипу, затем
    любое; лёгкое — первое подходящее по порядку (§6 п.4)."""
    candidates_order = windows
    if heavy:
        chrono_windows = [w for w in windows if _overlaps_chronotype(w, chronotype)]
        candidates_order = chrono_windows + [w for w in windows if w not in chrono_windows]

    for start, end in candidates_order:
        if heavy and chronotype in CHRONOTYPE_WINDOWS and _overlaps_chronotype((start, end), chronotype):
            b_start, b_end = CHRONOTYPE_WINDOWS[chronotype]
            slot_start = max(start, b_start)
            if slot_start + duration <= min(end, b_end) and slot_start + duration <= end:
                return (slot_start, slot_start + duration)
        if end - start >= duration:
            return (start, start + duration)
    return None


def _consume_window(windows: list[tuple[int, int]], start: int, end: int) -> list[tuple[int, int]]:
    """Убирает занятый интервал [start, end) из списка окон, оставляя
    остатки по краям (если они всё ещё >= MIN_WINDOW_MINUTES)."""
    result: list[tuple[int, int]] = []
    for w_start, w_end in windows:
        if end <= w_start or start >= w_end:
            result.append((w_start, w_end))
            continue
        if start > w_start and start - w_start >= MIN_WINDOW_MINUTES:
            result.append((w_start, start))
        if end < w_end and w_end - end >= MIN_WINDOW_MINUTES:
            result.append((end, w_end))
    return result


def parse_hhmm(value: str) -> int:
    """"HH:MM" -> минуты от полуночи."""
    h, m = value.split(":")
    return int(h) * 60 + int(m)


def format_hhmm(minutes: int) -> str:
    """Минуты от полуночи -> "HH:MM" (с учётом перехода через полночь)."""
    minutes = minutes % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def ensure_weekly_rest_day(
    heavy_by_day: dict[int, bool], min_rest_days: int = 1
) -> list[int]:
    """§6 п.5: минимум min_rest_days дней в неделю без тяжёлой нагрузки.
    Возвращает номера дней (1..7), которые нужно понизить до минимальной
    версии, если тяжёлые дни заняли всю неделю."""
    heavy_days = sorted(d for d, heavy in heavy_by_day.items() if heavy)
    rest_days = [d for d, heavy in heavy_by_day.items() if not heavy]
    if len(rest_days) >= min_rest_days or not heavy_days:
        return []
    # Не хватает дней отдыха — освобождаем последние по порядку тяжёлые дни.
    need = min_rest_days - len(rest_days)
    return heavy_days[-need:]
