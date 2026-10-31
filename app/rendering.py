"""
Общий рендеринг шаблонов: добавляет в контекст функцию перевода `t()` и
накопленные flash-уведомления, чтобы не повторять это в каждом роуте.
"""

import json
from typing import Optional

from fastapi import Request
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app.i18n import DEFAULT_LANGUAGE, translate
from app.services.flash import pop_flashes

templates = Jinja2Templates(directory="app/templates")


def _tojson(value) -> Markup:
    """Jinja2 (в отличие от Flask) не регистрирует `tojson` сам — нужен для
    безопасной передачи переведённых строк в инлайн-скрипты (тур по §…)."""
    return Markup(json.dumps(value, ensure_ascii=False))


templates.env.filters["tojson"] = _tojson


def render(
    request: Request,
    name: str,
    context: Optional[dict] = None,
    status_code: int = 200,
):
    """Рендерит шаблон с переводами текущего языка и flash-уведомлениями."""
    full_context = dict(context or {})
    lang = full_context.get("lang") or DEFAULT_LANGUAGE
    full_context["lang"] = lang
    full_context["t"] = lambda key, **kw: translate(lang, key, **kw)
    full_context["flashes"] = pop_flashes(request)

    return templates.TemplateResponse(request, name, full_context, status_code=status_code)
