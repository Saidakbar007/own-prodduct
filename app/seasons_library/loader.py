"""
Загрузка и валидация библиотеки шаблонов сезонов (§5 ТЗ) из YAML-файлов в
этом каталоге, плюс ИИ-сгенерированные "свои цели" (Фаза 4, §5): они живут
в таблице custom_template_draft, а не файлами — черновик доступен сразу
(в памяти этого процесса, пока человек проходит онбординг), утверждённый
админом — подхватывается для всех при следующем запросе через load_library().
"""

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from app.seasons.schema import SeasonTemplate

if TYPE_CHECKING:
    from sqlmodel import Session

_DIR = Path(__file__).parent
_CUSTOM_TEMPLATES: dict[str, SeasonTemplate] = {}


def template_files() -> list[Path]:
    """Все YAML-файлы библиотеки, отсортированные по имени."""
    return sorted(_DIR.glob("*.yaml"))


def load_template(path: Path) -> SeasonTemplate:
    """Загружает и валидирует один файл шаблона."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SeasonTemplate.model_validate(data)


@lru_cache(maxsize=1)
def load_library() -> dict[str, SeasonTemplate]:
    """Все шаблоны библиотеки (только файловые), ключ — id шаблона."""
    library: dict[str, SeasonTemplate] = {}
    for path in template_files():
        template = load_template(path)
        if template.id != path.stem:
            raise ValueError(f"{path.name}: id '{template.id}' не совпадает с именем файла")
        if template.id in library:
            raise ValueError(f"Повторяющийся id шаблона сезона: {template.id}")
        library[template.id] = template
    return library


def register_custom_template(template: SeasonTemplate) -> None:
    """ИИ только что сгенерировала этот шаблон — делаем его сразу доступным
    в этом процессе (чтобы онбординг мог продолжить baseline/schedule/trailer
    тем же template_id без похода в БД на каждый шаг)."""
    _CUSTOM_TEMPLATES[template.id] = template


def load_approved_custom_templates(db: "Session") -> None:
    """Подхватывает утверждённые админом черновики из БД (для процессов, где
    их ещё нет в памяти — например, после рестарта сервиса)."""
    from sqlmodel import select

    from app.models import CustomTemplateDraft

    rows = db.exec(select(CustomTemplateDraft).where(CustomTemplateDraft.approved.is_(True))).all()
    for row in rows:
        if row.template_id not in _CUSTOM_TEMPLATES:
            try:
                _CUSTOM_TEMPLATES[row.template_id] = SeasonTemplate.model_validate(
                    yaml.safe_load(row.template_yaml)
                )
            except Exception:
                continue


def get_template(template_id: str) -> SeasonTemplate:
    """Один шаблон по id (библиотечный или ИИ-сгенерированный, зарегистрированный
    через register_custom_template/load_approved_custom_templates); KeyError с
    понятным сообщением, если не найден нигде."""
    if template_id in _CUSTOM_TEMPLATES:
        return _CUSTOM_TEMPLATES[template_id]
    try:
        return load_library()[template_id]
    except KeyError:
        raise KeyError(f"Шаблон сезона не найден: {template_id}") from None
