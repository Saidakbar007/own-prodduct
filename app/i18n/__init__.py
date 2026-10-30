"""
Каркас локализации (§11 ТЗ). Строки — в app/i18n/ru.json и app/i18n/uz.json.
Сейчас: полный `ru`, каркас `uz` — будет дополняться по мере появления экранов.
Отсутствующий в uz ключ падает обратно на ru; отсутствующий нигде — возвращает
сам ключ (чтобы отсутствие перевода было видно, а не падало с ошибкой).
"""

import json
from pathlib import Path
from typing import Any

_DIR = Path(__file__).parent
_CACHE: dict[str, dict[str, str]] = {}

SUPPORTED_LANGUAGES = ("ru", "uz")
DEFAULT_LANGUAGE = "ru"


def _load(lang: str) -> dict[str, str]:
    if lang not in _CACHE:
        path = _DIR / f"{lang}.json"
        _CACHE[lang] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return _CACHE[lang]


def translate(lang: str, key: str, **kwargs: Any) -> str:
    """Переводит ключ на `lang`; откат на ru, затем на сам ключ."""
    strings = _load(lang)
    if key not in strings and lang != DEFAULT_LANGUAGE:
        strings = _load(DEFAULT_LANGUAGE)
    text = strings.get(key, key)
    return text.format(**kwargs) if kwargs else text
