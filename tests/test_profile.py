"""Тесты профиля: изменение своих данных, недоступность чужих."""

from tests.conftest import register_user


def test_update_own_profile(client):
    register_user(client, login="eva", mail="eva@example.com")
    resp = client.post(
        "/profile",
        data={"weight": 60.5, "hight": 170, "familly_stat": "single"},
    )
    assert resp.status_code == 200
    assert "Сохранено" in resp.text
    assert "60.5" in resp.text


def test_other_users_data_is_not_mixed_up(client, session):
    from sqlmodel import select

    from app.models import User

    register_user(client, login="frank", mail="frank@example.com")
    client.post("/profile", data={"weight": 80, "hight": 180, "familly_stat": "married"})
    client.get("/logout")

    register_user(client, login="grace", mail="grace@example.com")
    grace_profile = client.get("/profile")
    assert 'value="80' not in grace_profile.text  # вес Фрэнка не попал в поле ввода Грейс

    frank = session.exec(select(User).where(User.login == "frank")).first()
    grace = session.exec(select(User).where(User.login == "grace")).first()
    assert frank.weight == 80
    assert grace.weight is None
