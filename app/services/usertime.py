"""
Часовой пояс пользователя. "Сегодня" для отметок и серий считается по
серверному времени, сконвертированному в пояс пользователя — не по UTC
и не по времени клиента (клиент мог бы подделать своё "сегодня").
Менять пояс можно не чаще раза в 30 дней.
"""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models import User

DEFAULT_TIMEZONE = "UTC"
TIMEZONE_CHANGE_COOLDOWN_DAYS = 30


def is_valid_timezone(tz_name: str) -> bool:
    try:
        ZoneInfo(tz_name)
        return True
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return False


def _zone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def now_for(user: User) -> datetime:
    """Текущее серверное время (UTC), показанное в поясе пользователя."""
    return datetime.now(timezone.utc).astimezone(_zone(user.timezone))


def today_for(user: User) -> date:
    """"Сегодня" пользователя — серверное время в его часовом поясе."""
    return now_for(user).date()


def local_date(user: User, moment: datetime) -> date:
    """Переводит момент времени (UTC) в дату по поясу пользователя."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(_zone(user.timezone)).date()


def can_change_timezone(user: User) -> bool:
    """Можно менять пояс не чаще раза в TIMEZONE_CHANGE_COOLDOWN_DAYS дней."""
    if not user.timezone_changed_at:
        return True
    changed_at = user.timezone_changed_at
    if changed_at.tzinfo is None:
        changed_at = changed_at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - changed_at).days >= TIMEZONE_CHANGE_COOLDOWN_DAYS
