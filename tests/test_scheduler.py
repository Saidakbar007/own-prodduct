"""Планировщик дня/недели (§6 docs/specs/NEWLIFE_V8_SPEC.md) — таблицы случаев."""

import pytest

from app.newlife import scheduler as sch


# ------------------------------------------------------------- free_windows

def test_free_windows_whole_day_when_no_fixed_blocks():
    assert sch.free_windows(420, 1380, []) == [(420, 1380)]


def test_free_windows_gap_between_two_fixed_blocks():
    blocks = [
        sch.FixedBlock(400, 450, "commitment", "Пары"),
        sch.FixedBlock(700, 1000, "commitment", "Работа"),
    ]
    assert sch.free_windows(0, 1000, blocks) == [(0, 400), (450, 700)]


def test_free_windows_drops_windows_shorter_than_minimum():
    blocks = [sch.FixedBlock(10, 1370, "commitment", "Почти весь день")]
    # Остаются окна по 10 минут с обеих сторон — ровно граница, не отбрасываются
    assert sch.free_windows(0, 1380, blocks, min_window=10) == [(0, 10), (1370, 1380)]
    # Порог 11 минут — оба окна по 10 минут уже слишком короткие
    assert sch.free_windows(0, 1380, blocks, min_window=11) == []


def test_free_windows_clips_blocks_outside_day_range():
    # Сон "за кадром" (до дня и после) не должен создавать лишних окон
    blocks = [sch.FixedBlock(0, 420, "sleep", "Сон"), sch.FixedBlock(1380, 1440, "sleep", "Сон")]
    assert sch.free_windows(420, 1380, blocks) == [(420, 1380)]


# ------------------------------------------------------------ build_day_schedule

def _habit(title="Привычка", duration=20, heavy=False, minimal=None):
    return sch.Candidate(
        kind="habit", title=title, duration_min=duration, ref_type="habit", ref_id=1,
        heavy=heavy, minimal_duration_min=minimal,
    )


def test_simple_candidate_placed_at_window_start():
    result = sch.build_day_schedule([], 420, 1380, [], [_habit(duration=20)], [], daily_minutes_limit=60)
    assert len(result.blocks) == 1
    assert result.blocks[0].start_min == 420
    assert result.blocks[0].end_min == 440
    assert not result.unplaced


def test_daily_minutes_budget_blocks_second_candidate_without_minimal():
    habits = [_habit("A", duration=20), _habit("B", duration=20)]
    result = sch.build_day_schedule([], 420, 1380, [], habits, [], daily_minutes_limit=30)
    assert [b.title for b in result.blocks] == ["A"]
    assert [c.title for c in result.unplaced] == ["B"]
    assert "B" in result.messages[0]


def test_daily_minutes_budget_falls_back_to_minimal_version():
    habits = [_habit("A", duration=20), _habit("B", duration=20, minimal=5)]
    result = sch.build_day_schedule([], 420, 1380, [], habits, [], daily_minutes_limit=30)
    titles = {b.title: b for b in result.blocks}
    assert titles["B"].is_minimal is True
    assert titles["B"].end_min - titles["B"].start_min == 5
    assert not result.unplaced


def test_buffer_ratio_reserves_15_percent_of_free_time():
    # Один час свободен (0..60), запас 15% -> бюджет = 51 минута
    habit = _habit(duration=52)
    result = sch.build_day_schedule([], 0, 60, [], [habit], [], daily_minutes_limit=200, buffer_ratio=0.15)
    assert result.unplaced == [habit]


def test_heavy_candidate_prefers_chronotype_window_over_earlier_one():
    blocks = [sch.FixedBlock(200, 700, "commitment", "Занято")]  # делит день на (0,200) и (700,1000)
    heavy = sch.Candidate(
        kind="goal_action", title="Тренировка", duration_min=30, ref_type="season_day", ref_id=1, heavy=True,
    )
    result = sch.build_day_schedule(blocks, 0, 1000, [heavy], [], [], chronotype="day", daily_minutes_limit=60)
    # chronotype "day" = 660..1020 -> пересекается только с окном (700,1000)
    assert result.blocks[0].start_min == 700


def test_light_candidate_takes_first_chronological_window_regardless_of_chronotype():
    blocks = [sch.FixedBlock(200, 700, "commitment", "Занято")]
    light = _habit("Чтение", duration=15, heavy=False)
    result = sch.build_day_schedule(blocks, 0, 1000, [], [light], [], chronotype="day", daily_minutes_limit=60)
    assert result.blocks[0].start_min == 0


def test_tasks_sorted_by_eisenhower_then_deadline():
    tasks = [
        sch.Candidate(kind="task", title="drop-task", duration_min=10, ref_type="task", ref_id=1, eisenhower="drop"),
        sch.Candidate(kind="task", title="do-far", duration_min=10, ref_type="task", ref_id=2, eisenhower="do", deadline_days=5),
        sch.Candidate(kind="task", title="do-near", duration_min=10, ref_type="task", ref_id=3, eisenhower="do", deadline_days=1),
    ]
    result = sch.build_day_schedule([], 0, 1000, [], [], tasks, daily_minutes_limit=1000)
    assert [b.title for b in result.blocks] == ["do-near", "do-far", "drop-task"]


def test_tasks_do_not_count_against_daily_minutes_budget():
    # Бюджет на РАЗВИТИЕ (действия/привычки) не должен блокировать задачи —
    # задачи идут отдельным потоком дел, не "развитие".
    habit = _habit("Привычка", duration=20)
    task = sch.Candidate(kind="task", title="Задача", duration_min=500, ref_type="task", ref_id=1, eisenhower="do")
    result = sch.build_day_schedule([], 0, 1000, [], [habit], [task], daily_minutes_limit=20)
    assert {b.title for b in result.blocks} == {"Привычка", "Задача"}


def test_nothing_fits_even_minimal_is_reported_as_unplaced():
    blocks = [sch.FixedBlock(0, 995, "commitment", "Почти весь день")]  # окно всего 5 минут
    habit = _habit("Йога", duration=20, minimal=10)
    result = sch.build_day_schedule(blocks, 0, 1000, [], [habit], [], daily_minutes_limit=60)
    assert result.unplaced == [habit]
    assert "Йога" in result.messages[0]
    assert "перенесено" in result.messages[0]


def test_sleep_block_is_never_a_candidate_window():
    sleep = sch.FixedBlock(0, 420, "sleep", "Сон")
    windows = sch.free_windows(0, 1440, [sleep])
    assert all(w[0] >= 420 for w in windows)


# --------------------------------------------------------- ensure_weekly_rest_day

def test_ensure_weekly_rest_day_no_action_when_rest_already_present():
    heavy_by_day = {1: True, 2: True, 3: False, 4: True, 5: True, 6: False, 7: False}
    assert sch.ensure_weekly_rest_day(heavy_by_day) == []


def test_ensure_weekly_rest_day_frees_last_heavy_days_when_none_free():
    heavy_by_day = {d: True for d in range(1, 8)}
    assert sch.ensure_weekly_rest_day(heavy_by_day, min_rest_days=1) == [7]


def test_ensure_weekly_rest_day_no_heavy_days_needs_no_action():
    heavy_by_day = {d: False for d in range(1, 8)}
    assert sch.ensure_weekly_rest_day(heavy_by_day) == []


def test_ensure_weekly_rest_day_can_require_more_than_one():
    heavy_by_day = {d: True for d in range(1, 8)}
    assert sch.ensure_weekly_rest_day(heavy_by_day, min_rest_days=2) == [6, 7]
