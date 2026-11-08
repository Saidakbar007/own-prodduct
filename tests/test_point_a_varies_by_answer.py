"""
NEWLIFE_2_0.md Этап 1 п.4: «Точка А всегда одинаковая». Юнит-уровень
(app/newlife/point_a.py) уже покрыт tests/test_point_a.py. Этот файл
проверяет весь настоящий HTTP-путь онбординга — /onboarding/spheres ->
/onboarding/sphere-level -> .../register -> итоговый SphereState.level
в базе и текст точки А на экране раскрытия (/onboarding/trailer) — чтобы
поймать именно баг «ответы не сохраняются/игнорируются по дороге», а не
только саму формулу перевода ответа в уровень.

Расследование (см. отчёт backend-core): прогон этого сценария вручную
через TestClient с разными option_index показал РАЗНЫЕ уровни и разную
ширину полосы на /onboarding/trailer — сама цепочка онбординга и
point_a.py работают корректно при живой cookie-сессии. Если баг
воспроизводится у реального пользователя, подозреваемая причина — та же,
что и в «Аккаунт не сохраняется» (SessionMiddleware, см.
tests/test_session_persistence.py): если сессия не долетает между
запросами онбординга, draft каждый раз пустой и level откатывается на
дефолт 4 для любого ответа — то есть "всегда одинаковая".
"""

from datetime import date

import pytest
from sqlmodel import select

from app.models import SphereState, User
from app.newlife import point_a

THIS_YEAR = date.today().year


def _register_payload(unique: str):
    return {
        "name": "Точка А Тест",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"pa-{unique}@example.com",
        "login": f"pa-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }


@pytest.mark.parametrize("option_index", [0, 1, 2, 3])
def test_different_sphere_level_answers_produce_different_stored_levels(
    client, unique, db_session, option_index
):
    """Разные ответы на вопрос точки А сферы "body" -> разный
    SphereState.level в базе после регистрации."""
    login = f"{unique}-{option_index}"
    client.post("/onboarding/spheres", data={"sphere_ids": ["body"]})
    client.post("/onboarding/sphere-level", data={"option_index": option_index})
    reg = client.post(
        "/register",
        data=_register_payload(login),
        follow_redirects=True,
    )
    assert reg.status_code == 200

    user = db_session.exec(select(User).where(User.login == f"pa-{login}")).first()
    state = db_session.exec(
        select(SphereState).where(SphereState.uid == user.id, SphereState.sphere_id == "body")
    ).first()

    expected_level = point_a.question_for("body").options[option_index].level
    assert state is not None
    assert state.level == expected_level


def test_body_question_options_have_distinct_levels():
    """Гарантия, что вопрос реально МОЖЕТ дать разные уровни (если бы все
    варианты вели в один уровень, предыдущий тест бы не поймал регресс)."""
    question = point_a.question_for("body")
    levels = {opt.level for opt in question.options}
    assert len(levels) >= 3, "варианты вопроса точки А дают слишком мало разных уровней"


def test_trailer_screen_shows_different_level_text_for_different_answers(client, unique):
    """Экран раскрытия (/onboarding/trailer) показывает разную цифру/ширину
    полосы паутинки для разных ответов — не один и тот же текст всегда."""
    client.post("/onboarding/spheres", data={"sphere_ids": ["body"]})
    client.post("/onboarding/sphere-level", data={"option_index": 0})
    low_trailer = client.get("/onboarding/trailer").text

    client.post("/onboarding/spheres", data={"sphere_ids": ["body"]})
    client.post("/onboarding/sphere-level", data={"option_index": 3})
    high_trailer = client.get("/onboarding/trailer").text

    low_level = point_a.question_for("body").options[0].level
    high_level = point_a.question_for("body").options[3].level
    assert low_level != high_level
    assert f"{low_level}/10" in low_trailer
    assert f"{high_level}/10" in high_trailer
    assert low_trailer != high_trailer
