"""Тесты друзей: заявка → принятие, прогресс друга виден после принятия."""

from sqlmodel import select

from app.models import Friend, User
from app.services.points import award_points
from tests.conftest import register_user


def test_request_then_accept_shows_friend_progress(client, session):
    register_user(client, login="xena", mail="xena@example.com")
    client.get("/logout")
    register_user(client, login="yuri", mail="yuri@example.com")
    client.get("/logout")

    # Xena отправляет заявку Yuri
    client.post("/login", data={"login": "xena", "password": "secret123"})
    client.post("/friends/request", data={"login": "yuri"})

    yuri = session.exec(select(User).where(User.login == "yuri")).first()
    award_points(session, yuri, 700)  # 700 XP = ур.6 = ранг "Ученик"

    client.get("/logout")
    client.post("/login", data={"login": "yuri", "password": "secret123"})

    pending = session.exec(select(Friend).where(Friend.status == "pending")).first()
    assert pending is not None

    accept = client.post(f"/friends/{pending.id}/accept")
    assert accept.status_code == 200
    assert "xena" in accept.text  # Yuri теперь видит Xena в друзьях

    friend = session.exec(select(Friend).where(Friend.id == pending.id)).first()
    assert friend.status == "accepted"

    client.get("/logout")
    client.post("/login", data={"login": "xena", "password": "secret123"})
    xena_friends_page = client.get("/friends")
    assert "yuri" in xena_friends_page.text
    assert "Ученик" in xena_friends_page.text  # Xena видит уровень Yuri


def test_cannot_accept_someone_elses_request(client, session):
    register_user(client, login="zack", mail="zack@example.com")
    client.get("/logout")
    register_user(client, login="amy", mail="amy@example.com")
    client.get("/logout")

    client.post("/login", data={"login": "zack", "password": "secret123"})
    client.post("/friends/request", data={"login": "amy"})
    client.get("/logout")

    pending = session.exec(select(Friend).where(Friend.status == "pending")).first()

    # Третий пользователь (не адресат) не должен смочь принять заявку
    register_user(client, login="bob2", mail="bob2@example.com")
    client.post(f"/friends/{pending.id}/accept")

    friend = session.exec(select(Friend).where(Friend.id == pending.id)).first()
    assert friend.status == "pending"


def test_duplicate_request_rejected(client):
    register_user(client, login="carl", mail="carl@example.com")
    client.get("/logout")
    register_user(client, login="dina", mail="dina@example.com")
    client.get("/logout")

    client.post("/login", data={"login": "carl", "password": "secret123"})
    client.post("/friends/request", data={"login": "dina"})
    resp = client.post("/friends/request", data={"login": "dina"})
    assert "уже существует" in resp.text
