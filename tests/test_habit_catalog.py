"""Каталоги привычек (§10) — валидны, ссылаются только на известные сферы/триггеры."""

from app.newlife.habit_catalog import (
    bad_habit_item_by_id,
    habit_item_by_id,
    load_bad_habit_catalog,
    load_habit_catalog,
    trigger_label,
)


def test_habit_catalog_has_around_forty_entries_covering_all_spheres():
    items = load_habit_catalog()
    assert len(items) >= 30
    covered = {s for item in items for s in item.spheres}
    from app.newlife.spheres import SPHERE_IDS

    assert covered == set(SPHERE_IDS)


def test_habit_catalog_ids_are_unique():
    items = load_habit_catalog()
    ids = [i.id for i in items]
    assert len(ids) == len(set(ids))


def test_every_habit_has_a_minimal_version():
    for item in load_habit_catalog():
        assert item.minimal.strip()


def test_bad_habit_catalog_loads_with_valid_triggers():
    triggers, bad_habits = load_bad_habit_catalog()
    assert len(triggers) >= 5
    assert len(bad_habits) >= 5
    trigger_ids = {t.id for t in triggers}
    for bh in bad_habits:
        assert set(bh.triggers) <= trigger_ids


def test_bad_habit_replacement_ids_point_to_real_habits():
    _, bad_habits = load_bad_habit_catalog()
    for bh in bad_habits:
        if bh.replacement_id:
            assert habit_item_by_id(bh.replacement_id) is not None, bh.id


def test_habit_item_by_id_lookup():
    item = habit_item_by_id("meditation")
    assert item is not None
    assert item.title == "Медитация"
    assert habit_item_by_id("does-not-exist") is None


def test_trigger_label_lookup():
    assert trigger_label("boredom") == "Скука"
    assert trigger_label("unknown-id") == "unknown-id"


def test_bad_habit_item_by_id_lookup():
    item = bad_habit_item_by_id("social_media_scroll")
    assert item is not None
    assert item.unit == "minutes"
