"""
Загрузка и валидация библиотеки шаблонов сезонов (§5 ТЗ) из YAML-файлов в
этом каталоге.
"""

from functools import lru_cache
from pathlib import Path

import yaml

from app.seasons.schema import SeasonTemplate

_DIR = Path(__file__).parent


def template_files() -> list[Path]:
    """Все YAML-файлы библиотеки, отсортированные по имени."""
    return sorted(_DIR.glob("*.yaml"))


def load_template(path: Path) -> SeasonTemplate:
    """Загружает и валидирует один файл шаблона."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SeasonTemplate.model_validate(data)


@lru_cache(maxsize=1)
def load_library() -> dict[str, SeasonTemplate]:
    """Все шаблоны библиотеки, ключ — id шаблона."""
    library: dict[str, SeasonTemplate] = {}
    for path in template_files():
        template = load_template(path)
        if template.id != path.stem:
            raise ValueError(f"{path.name}: id '{template.id}' не совпадает с именем файла")
        if template.id in library:
            raise ValueError(f"Повторяющийся id шаблона сезона: {template.id}")
        library[template.id] = template
    return library


def get_template(template_id: str) -> SeasonTemplate:
    """Один шаблон по id; KeyError с понятным сообщением, если не найден."""
    try:
        return load_library()[template_id]
    except KeyError:
        raise KeyError(f"Шаблон сезона не найден: {template_id}") from None
