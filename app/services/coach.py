"""
AI-коуч.

В MVP по умолчанию работает без ключа — выдаёт готовый совет по простым
правилам (на основе streak, очков и уровня).

Если в .env задан ANTHROPIC_API_KEY, вместо заглушки используется
настоящий ответ Claude. При любой ошибке вызова API происходит
откат на заглушку, чтобы страница не падала.
"""

import os


def _canned_advice(habits_count: int, best_streak: int, level_name: str, points: int) -> str:
    """Готовый совет по правилам — работает всегда, без API-ключа."""
    if habits_count == 0:
        return "У тебя пока нет привычек. Начни с одной маленькой — например, выпивать стакан воды утром."
    if best_streak == 0:
        return "Пока нет серии дней подряд. Отметь любую привычку сегодня, чтобы начать streak!"
    if best_streak >= 7:
        return f"Отличная серия — {best_streak} дней подряд! Уровень «{level_name}», {points} очков. Не останавливайся!"
    return f"Хорошее начало — {best_streak} {'день' if best_streak == 1 else 'дня'} подряд. Продолжай в том же духе!"


def get_coach_advice(
    habits_count: int,
    best_streak: int,
    level_name: str,
    points: int,
    question: str = None,
) -> str:
    """Возвращает совет коуча: через Claude API, если есть ключ, иначе — заглушку."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            user_message = (
                f"Я веду привычки в приложении. У меня {habits_count} привычек, "
                f"лучшая текущая серия дней подряд — {best_streak}, уровень «{level_name}» "
                f"({points} очков). "
            )
            if question:
                user_message += f"Вопрос от меня: {question}. "
            user_message += "Дай короткий (2-3 предложения) мотивационный совет на русском."

            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text
        except Exception:
            pass  # при любой ошибке API — используем заглушку ниже

    return _canned_advice(habits_count, best_streak, level_name, points)
