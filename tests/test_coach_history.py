"""Тесты истории переписки с AI-коучем (таблица coach_messages)."""

from sqlmodel import select

from app.models import CoachMessage, User
from tests.conftest import register_user


def test_first_visit_creates_welcome_message(client, session):
    register_user(client, login="hugo2", mail="hugo2@example.com")
    client.get("/coach")

    user = session.exec(select(User).where(User.login == "hugo2")).first()
    messages = session.exec(select(CoachMessage).where(CoachMessage.uid == user.id)).all()
    assert len(messages) == 1
    assert messages[0].role == "coach"


def test_question_and_answer_persist_across_requests(client, session):
    register_user(client, login="ivan2", mail="ivan2@example.com")
    client.get("/coach")  # создаёт приветствие
    client.post("/coach", data={"question": "Как мотивировать себя?"})

    user = session.exec(select(User).where(User.login == "ivan2")).first()
    messages = session.exec(
        select(CoachMessage).where(CoachMessage.uid == user.id).order_by(CoachMessage.time.asc())
    ).all()
    assert len(messages) == 3  # приветствие + вопрос + ответ
    assert messages[1].role == "user"
    assert messages[1].text == "Как мотивировать себя?"
    assert messages[2].role == "coach"

    # история видна и на следующем GET-запросе
    page = client.get("/coach")
    assert "Как мотивировать себя?" in page.text
