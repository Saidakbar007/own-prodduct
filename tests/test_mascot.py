"""Ведущий (§8) — банк реплик и состояния."""

import pytest

from app.services import mascot

EVENTS = list(mascot.EVENT_STATE.keys())


@pytest.mark.parametrize("event", EVENTS)
def test_phrase_for_ru_returns_nonempty_known_variant(event):
    import json

    data = json.loads(mascot._PATH.read_text(encoding="utf-8"))
    phrase = mascot.phrase_for(event, "ru")
    assert phrase in data["ru"][event]


@pytest.mark.parametrize("event", EVENTS)
def test_every_event_has_at_least_8_russian_variants(event):
    import json

    data = json.loads(mascot._PATH.read_text(encoding="utf-8"))
    assert len(data["ru"][event]) >= 8


def test_phrase_for_uz_falls_back_to_ru_when_missing():
    assert mascot.phrase_for("done", "fr") != ""


def test_unknown_event_returns_empty_string():
    assert mascot.phrase_for("not-a-real-event", "ru") == ""


def test_state_for_known_and_unknown_events():
    assert mascot.state_for("done") == "glad"
    assert mascot.state_for("skip") == "worried"
    assert mascot.state_for("totally-unknown") == "calm"
