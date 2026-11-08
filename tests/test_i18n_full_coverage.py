"""Полное покрытие uz.json: каждый ключ ru.json должен существовать в uz.json
(иначе интерфейс для узбекоязычных пользователей молча показывает русский)."""
import json
from pathlib import Path


def test_every_ru_key_has_a_uz_translation():
    base = Path(__file__).resolve().parent.parent / "app" / "i18n"
    ru = json.loads((base / "ru.json").read_text(encoding="utf-8"))
    uz = json.loads((base / "uz.json").read_text(encoding="utf-8"))
    missing = sorted(set(ru.keys()) - set(uz.keys()))
    assert not missing, f"В uz.json не хватает {len(missing)} ключей: {missing[:20]}..."
