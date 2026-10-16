"""Тесты недельного рейтинга друзей по очкам."""

from sqlmodel import select

from app.models import Friend, User
from app.services.points import award_points
from tests.conftest import register_user


def test_leaderboard_sorted_by_weekly_points(client, session):
    register_user(client, login="carmen", mail="carmen@example.com")
    client.get("/logout")
    register_user(client, login="derek", mail="derek@example.com")
    client.get("/logout")

    carmen = session.exec(select(User).where(User.login == "carmen")).first()
    derek = session.exec(select(User).where(User.login == "derek")).first()

    client.post("/login", data={"login": "carmen", "password": "secret123"})
    client.post("/friends/request", data={"login": "derek"})
    client.get("/logout")

    client.post("/login", data={"login": "derek", "password": "secret123"})
    pending = session.exec(select(Friend).where(Friend.status == "pending")).first()
    client.post(f"/friends/{pending.id}/accept")

    award_points(session, carmen, 30)
    award_points(session, derek, 90)

    page = client.get("/friends")
    leaderboard_section = page.text.split("Рейтинг за неделю")[1]
    # derek (90 очков) должен стоять выше carmen (30 очков) в рейтинге
    assert leaderboard_section.index("derek") < leaderboard_section.index("carmen")
