"""Каталог упражнений (content/exercises.yaml) — схема и загрузчик
app/newlife/exercise_catalog.py."""

from app.newlife.exercise_catalog import all_exercises, exercise_meta, load_exercises


def test_at_least_twenty_exercises_loaded():
    exercises = load_exercises()
    assert len(exercises) >= 20


def test_no_duplicate_exercise_ids():
    ids = [e.id for e in all_exercises()]
    assert len(ids) == len(set(ids))


def test_every_exercise_has_complete_bilingual_content():
    for ex in all_exercises():
        assert ex.muscles
        assert ex.equipment
        assert 2 <= len(ex.mistakes) <= 4
        for field in (ex.name, ex.technique, ex.easy_version, ex.hard_version, *ex.mistakes):
            assert field.ru.strip(), f"{ex.id}: пустое поле (ru)"
            assert field.uz.strip(), f"{ex.id}: пустое поле (uz)"


def test_exercise_meta_found_and_not_found():
    entry = exercise_meta("squat")
    assert entry is not None
    assert entry.muscles
    assert exercise_meta("does-not-exist") is None
