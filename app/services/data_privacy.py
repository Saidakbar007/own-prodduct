"""
Экспорт и удаление данных пользователя (доп. задача, см. docs/decisions/
DECISIONS.md → «Этап "Доделай" + guide + wger»): дженерик по метаданным
SQLModel (`SQLModel.metadata.tables`), а не ручной список моделей — новая
таблица со ссылкой на users.id подхватывается автоматически, не нужно
помнить добавить её сюда при каждой новой фиче.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import delete
from sqlalchemy import select as core_select
from sqlmodel import Session, SQLModel

from app.models import User


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _tables_referencing_users() -> list[tuple[Any, list[str]]]:
    """Все таблицы (кроме users), у которых есть хоть одна колонка с
    foreign key на users.id, и список имён этих колонок."""
    result = []
    for table in SQLModel.metadata.tables.values():
        if table.name == "users":
            continue
        cols = [c.name for c in table.columns if any(fk.target_fullname == "users.id" for fk in c.foreign_keys)]
        if cols:
            result.append((table, cols))
    return result


def export_user_data(db: Session, uid: int) -> dict:
    """JSON-сериализуемый словарь со всеми СОБСТВЕННЫМИ данными
    пользователя (колонка `uid` — он владелец записи), без пароля. Записи,
    где человек просто упомянут (например, вызов "Спорим?" от другого
    человека, где он to_uid) — не его собственные данные, не экспортируются."""
    user = db.get(User, uid)
    data: dict[str, Any] = {
        "user": {k: _json_safe(v) for k, v in user.model_dump().items() if k != "password_hash"}
    }
    for table, cols in _tables_referencing_users():
        if "uid" not in cols:
            continue
        rows = db.execute(core_select(table).where(table.c.uid == uid)).mappings().all()
        if rows:
            data[table.name] = [{k: _json_safe(v) for k, v in dict(row).items()} for row in rows]
    return data


def delete_user_account(db: Session, uid: int) -> None:
    """Удаляет пользователя и ВСЕ записи, которые на него ссылаются в любой
    роли (не только `uid` — ещё `from_uid`/`to_uid`/`disputed_by`/
    `winner_uid` и т.п.), иначе осталась бы запись с битой внешней связью
    на удалённого пользователя (видна другому участнику вызова/состава)."""
    for table, cols in _tables_referencing_users():
        for col in cols:
            db.execute(delete(table).where(table.c[col] == uid))
    db.execute(delete(User.__table__).where(User.__table__.c.id == uid))
    db.commit()
