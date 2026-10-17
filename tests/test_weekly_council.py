"""
Тесты "совета недели" (v6b): доступен с 10 ур. героя, только по
воскресеньям, 5 реплик (одна на личность), генерируется раз в неделю.
"""

from datetime import date, timedelta

from sqlmodel import select

from app.models import Level, User, WeeklyCouncilMessage
from app.routers.hero import _weekly_council
from app.services.levels import xp_for_level
from app.services.points import award_points
from app.services.streak import _week_key
from tests.conftest import register_user


def _set_hero_level(session, user, level_number: int) -> None:
    total_xp = sum(xp_for_level(level) for level in range(1, level_number))
    award_points(session, user, total_xp)


def test_council_none_below_level_10(client, session, monkeypatch):
    import app.routers.hero as hero_module

    register_user(client, login="council1", mail="council1@example.com")
    user = session.exec(select(User).where(User.login == "council1")).first()
    monkeypatch.setattr(hero_module, "today_for", lambda u: date(2026, 1, 18))  # воскресенье

    council = _weekly_council(session, user, hero_level=9)
    assert council is None


def test_council_none_on_non_sunday(client, session, monkeypatch):
    import app.routers.hero as hero_module

    register_user(client, login="council2", mail="council2@example.com")
    user = session.exec(select(User).where(User.login == "council2")).first()
    monkeypatch.setattr(hero_module, "today_for", lambda u: date(2026, 1, 19))  # понедельник

    council = _weekly_council(session, user, hero_level=15)
    assert council is None


def test_council_shows_five_personas_on_sunday_at_level_10(client, session, monkeypatch):
    import app.routers.hero as hero_module

    register_user(client, login="council3", mail="council3@example.com")
    user = session.exec(select(User).where(User.login == "council3")).first()
    monkeypatch.setattr(hero_module, "today_for", lambda u: date(2026, 1, 18))

    council = _weekly_council(session, user, hero_level=10)
    assert council is not None
    assert len(council) == 5
    names = {line["persona_name"] for line in council}
    assert names == {"Воин", "Мудрец", "Монах", "Целитель", "Бард"}


def test_council_generated_once_per_week(client, session, monkeypatch):
    import app.routers.hero as hero_module

    register_user(client, login="council4", mail="council4@example.com")
    user = session.exec(select(User).where(User.login == "council4")).first()
    monkeypatch.setattr(hero_module, "today_for", lambda u: date(2026, 1, 18))

    _weekly_council(session, user, hero_level=10)
    count_after_first = len(
        session.exec(
            select(WeeklyCouncilMessage).where(
                WeeklyCouncilMessage.uid == user.id, WeeklyCouncilMessage.week_key == _week_key(date(2026, 1, 18))
            )
        ).all()
    )
    _weekly_council(session, user, hero_level=10)
    count_after_second = len(
        session.exec(
            select(WeeklyCouncilMessage).where(
                WeeklyCouncilMessage.uid == user.id, WeeklyCouncilMessage.week_key == _week_key(date(2026, 1, 18))
            )
        ).all()
    )
    assert count_after_first == 5
    assert count_after_second == 5  # не задублировалось


def test_hero_page_shows_council_for_demo_like_user_on_sunday(client, session, monkeypatch):
    import app.routers.hero as hero_module

    register_user(client, login="council5", mail="council5@example.com")
    user = session.exec(select(User).where(User.login == "council5")).first()
    _set_hero_level(session, user, 10)
    monkeypatch.setattr(hero_module, "today_for", lambda u: date(2026, 1, 18))

    resp = client.get("/hero")
    assert resp.status_code == 200
    assert "Совет недели" in resp.text
