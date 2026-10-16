"""Тесты программ (Training/Education), привязанных к цели."""

from sqlmodel import select

from app.models import Education, Goal, Training, User
from tests.conftest import register_user


def _make_goal(client, session, login, mail):
    register_user(client, login=login, mail=mail)
    client.post("/goals", data={"name": "Мечта"})
    user = session.exec(select(User).where(User.login == login)).first()
    dream = session.exec(select(Goal).where(Goal.uid == user.id, Goal.parent_id == None)).first()  # noqa: E711
    client.post(f"/goals/{dream.id}/child", data={"name": "Цель"})
    return session.exec(select(Goal).where(Goal.parent_id == dream.id)).first()


def test_add_training_and_education(client, session):
    goal = _make_goal(client, session, "uma", "uma@example.com")

    resp = client.post(f"/goals/{goal.id}/training", data={"name": "Бег по утрам", "program": "5 км 3 раза в неделю"})
    assert resp.status_code == 200
    assert "Бег по утрам" in resp.text

    resp2 = client.post(f"/goals/{goal.id}/education", data={"name": "Курс FastAPI", "program": "20 уроков"})
    assert "Курс FastAPI" in resp2.text

    trainings = session.exec(select(Training).where(Training.g_id == goal.id)).all()
    educations = session.exec(select(Education).where(Education.g_id == goal.id)).all()
    assert len(trainings) == 1
    assert len(educations) == 1


def test_cannot_add_program_to_other_users_goal(client, session):
    goal = _make_goal(client, session, "vik", "vik@example.com")
    client.get("/logout")

    register_user(client, login="wendy", mail="wendy@example.com")
    client.post(f"/goals/{goal.id}/training", data={"name": "Чужая программа"})

    trainings = session.exec(select(Training).where(Training.g_id == goal.id)).all()
    assert trainings == []
