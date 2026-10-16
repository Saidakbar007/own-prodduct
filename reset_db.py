"""
Пересоздаёт базу данных с нуля: бэкап текущего app.db → применение миграций
с чистого листа → seed. Полезно, когда схема поменялась и миграции конфликтуют
со старыми данными на деве.

Запуск: python reset_db.py
"""

import os
import shutil
from datetime import datetime

DB_PATH = "app.db"


def backup_existing_db() -> str | None:
    """Копирует текущий app.db в app.db.bak-<дата> (если он есть). Возвращает путь к бэкапу."""
    if not os.path.exists(DB_PATH):
        return None
    backup_path = f"{DB_PATH}.bak-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def main() -> None:
    backup_path = backup_existing_db()
    if backup_path:
        print(f"Бэкап сохранён: {backup_path}")

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Старый {DB_PATH} удалён")

    from app.migrations_runner import run_migrations

    run_migrations()
    print("Миграции применены")

    import seed

    seed.main()


if __name__ == "__main__":
    main()
