"""«Состав» (§7.6, Фаза 3) — группировка, реакции, анонимность, выход."""

import itertools
from datetime import date, timedelta

from sqlmodel import select

# Монотонный счётчик недель — гарантирует, что ни один вызов _isolated_today
# не совпадёт ни с другим вызовом здесь, ни с today() из других тестовых
# файлов (которые создают сезоны на реальную сегодняшнюю дату, смещение 0).
_WEEK_OFFSET = itertools.count(start=1000)

from app.models import Squad, SquadMember
from app.services.seasons import create_season
from app.services.squads import (
    active_members,
    add_reaction,
    display_name,
    leave_squad,
    reaction_count,
    set_anonymous,
)


def _isolated_today(unique: str) -> date:
    """Каждый тест — в своей волне (иначе составы расшаренной тестовой базы
    конкурируют друг с другом за место в одном и том же squad)."""
    return date(2026, 11, 3) + timedelta(weeks=next(_WEEK_OFFSET))


def _make_user(db_session, login):
    from app.auth import hash_password
    from app.models import User

    user = User(
        login=login,
        email=f"{login}@example.com",
        password_hash=hash_password("pw"),
        name=f"Юзер {login}",
        birth_year=1995,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_two_users_same_wave_and_template_join_same_squad(db_session, unique):
    today = _isolated_today(unique)  # у обоих одна и та же ближайшая волна
    u1 = _make_user(db_session, f"squad-a-{unique}")
    u2 = _make_user(db_session, f"squad-b-{unique}")

    s1 = create_season(db_session, u1.id, "run_5k", 60, 5, today)
    s2 = create_season(db_session, u2.id, "run_5k", 60, 8, today)

    assert s1.wave_id == s2.wave_id

    members = db_session.exec(
        select(SquadMember).where(SquadMember.uid.in_([u1.id, u2.id]))
    ).all()
    squad_ids = {m.squad_id for m in members}
    assert len(squad_ids) == 1


def test_squad_caps_at_eight_members(db_session, unique):
    today = _isolated_today(unique)
    users = [_make_user(db_session, f"cap-{unique}-{i}") for i in range(9)]
    seasons = [create_season(db_session, u.id, "run_5k", 60, 5, today) for u in users]

    squad_ids = [
        db_session.exec(
            select(SquadMember.squad_id).where(SquadMember.uid == u.id, SquadMember.season_id == s.id)
        ).first()
        for u, s in zip(users, seasons)
    ]
    # первые 8 - в одном составе, девятый - в новом
    assert len(set(squad_ids[:8])) == 1
    assert squad_ids[8] != squad_ids[0]


def test_anonymous_display_name_vs_revealed(db_session, unique):
    today = _isolated_today(unique)
    u = _make_user(db_session, f"anon-{unique}")
    season = create_season(db_session, u.id, "run_5k", 60, 5, today)
    member = db_session.exec(
        select(SquadMember).where(SquadMember.uid == u.id, SquadMember.season_id == season.id)
    ).first()

    assert member.anonymous is True
    assert display_name(u, member) == f"Участник #{u.id:03d}"

    set_anonymous(db_session, u.id, member.squad_id, False)
    db_session.refresh(member)
    assert display_name(u, member) == u.name


def test_reaction_is_once_per_day_per_pair(db_session, unique):
    today = _isolated_today(unique)
    u1 = _make_user(db_session, f"react-a-{unique}")
    u2 = _make_user(db_session, f"react-b-{unique}")
    s1 = create_season(db_session, u1.id, "run_5k", 60, 5, today)
    create_season(db_session, u2.id, "run_5k", 60, 5, today)

    member1 = db_session.exec(
        select(SquadMember).where(SquadMember.uid == u1.id, SquadMember.season_id == s1.id)
    ).first()

    assert add_reaction(db_session, member1.squad_id, u1.id, u2.id, today) is True
    assert add_reaction(db_session, member1.squad_id, u1.id, u2.id, today) is False  # повторная в тот же день
    assert reaction_count(db_session, member1.squad_id, u2.id, today) == 1


def test_leave_squad_removes_from_active_members(db_session, unique):
    today = _isolated_today(unique)
    u1 = _make_user(db_session, f"leave-a-{unique}")
    u2 = _make_user(db_session, f"leave-b-{unique}")
    s1 = create_season(db_session, u1.id, "run_5k", 60, 5, today)
    create_season(db_session, u2.id, "run_5k", 60, 5, today)

    member1 = db_session.exec(
        select(SquadMember).where(SquadMember.uid == u1.id, SquadMember.season_id == s1.id)
    ).first()
    assert len(active_members(db_session, member1.squad_id)) == 2

    assert leave_squad(db_session, u1.id, member1.squad_id) is True
    assert len(active_members(db_session, member1.squad_id)) == 1
