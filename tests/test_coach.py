"""Тесты AI-коуча: работает без ключа (заглушка), реагирует на данные пользователя."""

import os

from sqlmodel import select

from app.models import User
from app.services.points import award_points
from tests.conftest import register_user


def test_coach_without_habits_suggests_starting(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    register_user(client, login="ewa", mail="ewa@example.com")
    resp = client.get("/coach")
    assert resp.status_code == 200
    assert "нет привычек" in resp.text


def test_coach_reacts_to_streak(client, session, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    register_user(client, login="finn", mail="finn@example.com")
    client.post("/habits", data={"name": "Чтение"})

    user = session.exec(select(User).where(User.login == "finn")).first()
    award_points(session, user, 50)

    resp = client.get("/coach")
    assert "серии дней подряд" in resp.text  # привычка есть, но ещё не отмечена


def test_coach_accepts_question_without_crashing(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    register_user(client, login="gina", mail="gina@example.com")
    resp = client.post("/coach", data={"question": "Как начать?"})
    assert resp.status_code == 200
    assert "Как начать?" in resp.text
