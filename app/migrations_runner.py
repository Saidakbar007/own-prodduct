"""
Применяет миграции Alembic программно — чтобы на старте приложения
(и на Render при деплое) не требовался ручной `alembic upgrade head`.
"""

import os

from alembic import command
from alembic.config import Config


def _alembic_config() -> Config:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config = Config(os.path.join(project_root, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(project_root, "migrations"))

    database_url = os.getenv("DATABASE_URL", "sqlite:///app.db")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def run_migrations() -> None:
    """Применяет все непримененные миграции (создаёт таблицы при первом запуске)."""
    command.upgrade(_alembic_config(), "head")
