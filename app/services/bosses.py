"""
Босс недели (v6b, доступен с 6-го уровня героя): один общий босс на всех
на неделю (детерминированная ротация по номеру ISO-недели), друзья
объединяются в группу и совместно наносят урон отметками привычек.
HP = 300 × участников. Победа до конца недели (пн-вс) — сундук и 30 монет
каждому участнику; не добили — группа истекает без штрафа.
"""

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import BossGroup, BossGroupMember, BossHit, Friend, User
from app.services.chests import grant_chest
from app.services.coins import award_coins
from app.services.streak import _week_key

BOSSES = {
    "laziness": "Лень",
    "procrastination": "Прокрастинация",
    "sleepiness": "Сонливость",
    "sugar": "Сахар",
    "scroll": "Скролл",
    "doubt": "Сомнение",
}
BOSS_CODES = list(BOSSES.keys())

BOSS_UNLOCK_HERO_LEVEL = 6
HP_PER_MEMBER = 300
VICTORY_COINS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def current_week_key() -> str:
    return _week_key(_now().date())


def boss_of_week(week_key: str) -> str:
    """Один общий босс на всех — детерминированная ротация по номеру ISO-недели."""
    iso_week = int(week_key.split("-W")[1])
    return BOSS_CODES[iso_week % len(BOSS_CODES)]


def expire_stale_groups(db: Session) -> None:
    """Группы прошлых недель, которые не победили босса, помечаются expired (без штрафа)."""
    week = current_week_key()
    stale = db.exec(
        select(BossGroup).where(BossGroup.status == "active", BossGroup.week_key != week)
    ).all()
    for group in stale:
        group.status = "expired"
        db.add(group)
    if stale:
        db.commit()


def active_group_for_user(db: Session, uid: int) -> BossGroup | None:
    """Активная (на текущей неделе) группа, в которой состоит пользователь."""
    week = current_week_key()
    membership = db.exec(select(BossGroupMember).where(BossGroupMember.uid == uid)).all()
    group_ids = [m.group_id for m in membership]
    if not group_ids:
        return None
    return db.exec(
        select(BossGroup).where(
            BossGroup.id.in_(group_ids), BossGroup.week_key == week, BossGroup.status == "active"
        )
    ).first()


def group_members(db: Session, group_id: int) -> list[BossGroupMember]:
    return db.exec(select(BossGroupMember).where(BossGroupMember.group_id == group_id)).all()


def create_group(db: Session, user: User, hero_level: int) -> tuple[BossGroup | None, str]:
    if hero_level < BOSS_UNLOCK_HERO_LEVEL:
        return None, f"Босс недели доступен с {BOSS_UNLOCK_HERO_LEVEL}-го уровня героя"
    if active_group_for_user(db, user.id):
        return None, "У тебя уже есть активная группа на этой неделе"

    week = current_week_key()
    group = BossGroup(
        week_key=week, boss_code=boss_of_week(week), hp_total=HP_PER_MEMBER, hp_remaining=HP_PER_MEMBER
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    db.add(BossGroupMember(group_id=group.id, uid=user.id))
    db.commit()
    return group, f"Группа создана — {BOSSES[group.boss_code]} ждёт!"


def _are_friends(db: Session, uid_a: int, uid_b: int) -> bool:
    return (
        db.exec(
            select(Friend).where(
                Friend.status == "accepted",
                ((Friend.uid == uid_a) & (Friend.friend_id == uid_b))
                | ((Friend.uid == uid_b) & (Friend.friend_id == uid_a)),
            )
        ).first()
        is not None
    )


def join_group(db: Session, user: User, group_id: int) -> tuple[bool, str]:
    group = db.get(BossGroup, group_id)
    if not group or group.status != "active" or group.week_key != current_week_key():
        return False, "Эта группа уже не активна"
    if active_group_for_user(db, user.id):
        return False, "У тебя уже есть активная группа на этой неделе"

    members = group_members(db, group_id)
    if not any(_are_friends(db, user.id, m.uid) for m in members):
        return False, "Присоединиться можно только к группе друга"

    group.hp_total += HP_PER_MEMBER
    group.hp_remaining += HP_PER_MEMBER
    db.add(group)
    db.add(BossGroupMember(group_id=group_id, uid=user.id))
    db.commit()
    return True, f"Ты присоединился к бою с «{BOSSES[group.boss_code]}»!"


def joinable_groups_for_user(db: Session, uid: int) -> list[BossGroup]:
    """Активные группы друзей пользователя на этой неделе, к которым можно присоединиться."""
    week = current_week_key()
    friends_ids = {
        f.friend_id if f.uid == uid else f.uid
        for f in db.exec(
            select(Friend).where(Friend.status == "accepted", (Friend.uid == uid) | (Friend.friend_id == uid))
        ).all()
    }
    if not friends_ids:
        return []

    member_rows = db.exec(select(BossGroupMember).where(BossGroupMember.uid.in_(friends_ids))).all()
    group_ids = {m.group_id for m in member_rows}
    if not group_ids:
        return []

    groups = db.exec(
        select(BossGroup).where(
            BossGroup.id.in_(group_ids), BossGroup.week_key == week, BossGroup.status == "active"
        )
    ).all()
    my_group = active_group_for_user(db, uid)
    groups = [g for g in groups if not my_group or g.id != my_group.id]

    # Группы, где все участники — тестовые аккаунты (/admin/sandbox), не
    # затягивают реальных друзей в бой с "ненастоящим" HP-пулом (v6d, п.19).
    real_groups = []
    for group in groups:
        member_uids = [m.uid for m in group_members(db, group.id)]
        members = [db.get(User, m_uid) for m_uid in member_uids]
        if any(m and not m.is_test for m in members):
            real_groups.append(group)
    return real_groups


def deal_damage(db: Session, user: User, damage: int) -> BossGroup | None:
    """
    Наносит урон активной группе пользователя (если есть) — damage = XP,
    который принесла отметка. Если HP добит — группа "won", награда всем.
    Возвращает группу, если удар был нанесён (для UI), иначе None.
    """
    if damage <= 0:
        return None
    group = active_group_for_user(db, user.id)
    if not group:
        return None

    group.hp_remaining = max(0, group.hp_remaining - damage)
    db.add(group)
    db.add(BossHit(group_id=group.id, uid=user.id, damage=damage))
    db.commit()

    if group.hp_remaining <= 0 and group.status == "active":
        group.status = "won"
        db.add(group)
        db.commit()
        for member in group_members(db, group.id):
            member_user = db.get(User, member.uid)
            if member_user:
                # Фиксированная награда за командную победу — без trust/harmony
                # множителей (см. DECISIONS.md, п.10), в отличие от обычных монет
                award_coins(db, member_user, VICTORY_COINS, apply_trust=False, apply_harmony=False)
                grant_chest(db, member_user, week_start=_now().date(), habit_id=None)

    db.refresh(group)
    return group


def hit_feed(db: Session, group_id: int, limit: int = 20) -> list[dict]:
    """Лента ударов участников — для показа на странице группы."""
    hits = db.exec(
        select(BossHit).where(BossHit.group_id == group_id).order_by(BossHit.time.desc()).limit(limit)
    ).all()
    result = []
    for hit in hits:
        user = db.get(User, hit.uid)
        result.append({"login": user.login if user else "?", "damage": hit.damage, "time": hit.time})
    return result


def boss_victories_count(db: Session, uid: int) -> int:
    """Число побеждённых боссов, в которых участвовал пользователь — для достижений."""
    member_rows = db.exec(select(BossGroupMember).where(BossGroupMember.uid == uid)).all()
    group_ids = [m.group_id for m in member_rows]
    if not group_ids:
        return 0
    return len(
        db.exec(select(BossGroup).where(BossGroup.id.in_(group_ids), BossGroup.status == "won")).all()
    )
