"""Каркас локализации (app/i18n)."""

from app.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, translate


def test_translate_known_key_in_russian():
    assert translate("ru", "common.app_name") == "Сезоны"


def test_translate_known_key_in_uzbek():
    assert translate("uz", "common.app_name") == "Mavsumlar"


def test_translate_falls_back_to_russian_when_language_file_is_incomplete():
    # для языка без файла переводов (или без конкретного ключа в нём) —
    # тихий откат на ru, а не ошибка и не пустая строка
    assert translate("fr", "common.app_name") == "Сезоны"


def test_translate_unknown_key_returns_the_key_itself():
    assert translate("ru", "nonexistent.key") == "nonexistent.key"


def test_translate_interpolates_kwargs():
    assert translate("ru", "home.logged_greeting", name="Диёр") == "Привет, Диёр"


def test_default_language_is_russian():
    assert DEFAULT_LANGUAGE == "ru"
    assert "ru" in SUPPORTED_LANGUAGES
    assert "uz" in SUPPORTED_LANGUAGES
