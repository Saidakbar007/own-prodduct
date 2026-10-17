"""
Тесты новой системы уровней/рангов (v6a): XP до следующего уровня = 80+20*L,
50 уровней, 5 рангов (1-5/6-15/16-25/26-40/41-50).
"""

from app.services.levels import (
    MAX_LEVEL,
    RANKS,
    level_for_xp,
    level_progress,
    rank_for_level,
    rank_index_for_level,
    xp_for_level,
)


def test_xp_for_level_formula():
    assert xp_for_level(1) == 100  # 80 + 20*1
    assert xp_for_level(5) == 180
    assert xp_for_level(49) == 1060


def test_level_for_xp_at_boundaries():
    assert level_for_xp(0) == 1
    assert level_for_xp(99) == 1
    assert level_for_xp(100) == 2  # 80+20*1 = ровно хватает на ур.2
    assert level_for_xp(219) == 2
    assert level_for_xp(220) == 3


def test_level_never_exceeds_max():
    assert level_for_xp(10**9) == MAX_LEVEL == 50


def test_level_never_negative():
    assert level_for_xp(-100) == 1


def test_ranks_cover_1_to_50_without_gaps_or_overlap():
    assert RANKS[0][0] == 1
    assert RANKS[-1][1] == 50
    seen = set()
    for low, high, _name in RANKS:
        for level in range(low, high + 1):
            assert level not in seen, f"уровень {level} попадает в два ранга"
            seen.add(level)
    assert seen == set(range(1, 51))


def test_rank_names_match_spec():
    assert rank_for_level(1) == "Новичок"
    assert rank_for_level(5) == "Новичок"
    assert rank_for_level(6) == "Ученик"
    assert rank_for_level(15) == "Ученик"
    assert rank_for_level(16) == "Практик"
    assert rank_for_level(25) == "Практик"
    assert rank_for_level(26) == "Мастер"
    assert rank_for_level(40) == "Мастер"
    assert rank_for_level(41) == "Легенда"
    assert rank_for_level(50) == "Легенда"


def test_rank_index_is_stage_1_to_5():
    assert rank_index_for_level(1) == 1
    assert rank_index_for_level(10) == 2
    assert rank_index_for_level(20) == 3
    assert rank_index_for_level(30) == 4
    assert rank_index_for_level(45) == 5


def test_level_progress_within_level():
    progress = level_progress(50)  # уровень 1, 50/100 XP в него
    assert progress["level"] == 1
    assert progress["rank"] == "Новичок"
    assert progress["stage"] == 1
    assert progress["xp_into_level"] == 50
    assert progress["xp_for_next_level"] == 100
    assert progress["percent"] == 50
    assert progress["next_rank"] is None  # ур.2 ещё в том же ранге


def test_level_progress_flags_next_rank_change():
    progress = level_progress(699)  # ур.5, последний уровень ранга "Новичок"
    assert progress["level"] == 5
    assert progress["rank"] == "Новичок"
    assert progress["next_rank"] == "Ученик"


def test_level_progress_at_max_level():
    progress = level_progress(10**9)
    assert progress["level"] == 50
    assert progress["percent"] == 100
    assert progress["xp_for_next_level"] is None
    assert progress["next_rank"] is None
