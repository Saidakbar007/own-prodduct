"""ИИ-генерация "своей цели" (§5, Фаза 4) — без реальных вызовов API."""

import pytest
from sqlmodel import select

from app.models import CustomTemplateDraft
from app.services import custom_goal_ai
from app.seasons_library.loader import _CUSTOM_TEMPLATES, get_template

VALID_YAML = """```yaml
id: placeholder
version: 1
title: "Сезон: научиться плавать"
title_uz: "Mavsum: suzishni o'rganish"
category: fitness
metric: {name: "Непрерывное плавание", unit: "м", direction: up}
lengths: [30, 60]
target_default: 200
baseline_test:
  prompt: "Сколько метров ты можешь проплыть без остановки?"
  input: number
  min: 0
  max: 500
eligibility:
  min_age: 18
  warnings: []
schedule: {train_days: [2, 4, 6], minutes: [20, 40]}
phases:
  - phase: 1
    unlock_if_baseline_gte: 0
    days:
      - title: "Техника на месте"
        instructions: "Разминка, отработка техники у бортика."
        minimal: "10 минут в воде"
        expected_progress: 5
rest_day: {title: "Отдых", instructions: "Лёгкая растяжка"}
measure_every_days: 7
measure: {prompt: "Сколько метров проплыл(а)?", proof: optional, progress_photo: false}
safety: {max_phase_jump: 1, rest_days_min_per_week: 1}
```"""

INVALID_YAML = "```yaml\nnot: [valid, schema\n```"


@pytest.fixture(autouse=True)
def _clear_custom_cache():
    _CUSTOM_TEMPLATES.clear()
    yield
    _CUSTOM_TEMPLATES.clear()


def test_extract_yaml_strips_code_fence():
    assert custom_goal_ai._extract_yaml(VALID_YAML).startswith("id: placeholder")


def test_parse_and_validate_accepts_well_formed_yaml():
    template = custom_goal_ai.parse_and_validate(VALID_YAML, "научиться плавать")
    assert template is not None
    assert template.id.startswith("custom_")
    assert template.metric.unit == "м"


def test_parse_and_validate_rejects_broken_yaml():
    assert custom_goal_ai.parse_and_validate(INVALID_YAML, "что угодно") is None


def test_generate_with_ai_succeeds_on_first_try(db_session, monkeypatch):
    calls = []

    def fake_call_model(goal_text):
        calls.append(goal_text)
        return VALID_YAML

    monkeypatch.setattr(custom_goal_ai, "call_model", fake_call_model)

    goal_text = "научиться плавать кролем на спине"
    template = custom_goal_ai.generate_with_ai(db_session, goal_text)
    assert template is not None
    assert len(calls) == 1

    draft = db_session.exec(
        select(CustomTemplateDraft).where(CustomTemplateDraft.template_id == template.id)
    ).first()
    assert draft is not None
    assert draft.template_id == template.id

    # шаблон сразу доступен через обычный get_template
    assert get_template(template.id).metric.unit == "м"


def test_generate_with_ai_retries_once_then_succeeds(db_session, monkeypatch):
    responses = iter([INVALID_YAML, VALID_YAML])
    monkeypatch.setattr(custom_goal_ai, "call_model", lambda goal_text: next(responses))

    template = custom_goal_ai.generate_with_ai(db_session, "научиться плавать быстро")
    assert template is not None


def test_generate_with_ai_gives_up_after_two_bad_responses(db_session, monkeypatch):
    monkeypatch.setattr(custom_goal_ai, "call_model", lambda goal_text: INVALID_YAML)

    goal_text = "что-то странное и не встречавшееся раньше в этих тестах"
    template = custom_goal_ai.generate_with_ai(db_session, goal_text)
    assert template is None

    key = custom_goal_ai._cache_key(goal_text)
    existing = db_session.exec(
        select(CustomTemplateDraft).where(CustomTemplateDraft.goal_text_hash == key)
    ).first()
    assert existing is None


def test_generate_with_ai_uses_cache_without_calling_model_again(db_session, monkeypatch):
    calls = []
    monkeypatch.setattr(
        custom_goal_ai, "call_model", lambda goal_text: (calls.append(1), VALID_YAML)[1]
    )

    goal_text = "научиться плавать баттерфляем без задержки дыхания"
    first = custom_goal_ai.generate_with_ai(db_session, goal_text)
    assert len(calls) == 1

    _CUSTOM_TEMPLATES.clear()  # имитируем новый процесс/сессию — в памяти пусто
    second = custom_goal_ai.generate_with_ai(db_session, goal_text)
    assert len(calls) == 1  # второй раз модель не вызывалась — отдали из БД-кэша
    assert first.id == second.id


def test_generate_with_ai_survives_model_call_exception(db_session, monkeypatch):
    def boom(goal_text):
        raise RuntimeError("network down")

    monkeypatch.setattr(custom_goal_ai, "call_model", boom)
    assert custom_goal_ai.generate_with_ai(db_session, "что угодно") is None
