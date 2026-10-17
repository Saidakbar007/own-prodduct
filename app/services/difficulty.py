"""
Антинакрутка очков: сложность "своей" привычки считает сервер — по
ключевым словам и количественной цели (минуты/км/шаги), а если задан
ANTHROPIC_API_KEY — через Claude. Пользователь может только занизить
предложенную сложность, но не завысить её.
"""

import os
import re

DIFFICULTY_RANK = {"easy": 0, "medium": 1, "hard": 2}
RANK_TO_DIFFICULTY = {0: "easy", 1: "medium", 2: "hard"}

HARD_KEYWORDS = [
    "зал", "марафон", "никогда", "полностью откажись", "6 утра", "холодный душ",
    "каждый час", "весь день", "целый день",
]
EASY_KEYWORDS = ["немного", "хотя бы", "стакан", "минимум", "чуть-чуть", "пару минут"]


def _numbers(text: str) -> list[int]:
    return [int(n) for n in re.findall(r"\d+", text)]


def calculate_difficulty_by_rules(name: str, description: str = None) -> str:
    """Простые правила по ключевым словам и числовой цели (минуты/км/шаги)."""
    text = f"{name} {description or ''}".lower()

    if any(kw in text for kw in HARD_KEYWORDS):
        return "hard"
    if any(kw in text for kw in EASY_KEYWORDS):
        return "easy"

    numbers = _numbers(text)
    if numbers:
        value = max(numbers)
        if "минут" in text or "мин" in text:
            if value <= 10:
                return "easy"
            return "medium" if value <= 30 else "hard"
        if "шаг" in text:
            if value <= 3000:
                return "easy"
            return "medium" if value <= 8000 else "hard"
        if "км" in text:
            if value <= 2:
                return "easy"
            return "medium" if value <= 7 else "hard"

    return "medium"  # по умолчанию, если не удалось определить по тексту


def calculate_difficulty(name: str, description: str = None) -> str:
    """
    Определяет сложность привычки. Если задан ANTHROPIC_API_KEY — пробует
    спросить Claude, иначе (или при ошибке) — правила по ключевым словам.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=10,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Привычка: «{name}». Описание: «{description or ''}». "
                        "Оцени сложность выполнения этой привычки каждый день: "
                        "easy, medium или hard. Ответь ровно одним словом без пояснений."
                    ),
                }],
            )
            text = response.content[0].text.strip().lower()
            if text in DIFFICULTY_RANK:
                return text
        except Exception:
            pass

    return calculate_difficulty_by_rules(name, description)


def clamp_difficulty(claimed: str, calculated: str) -> str:
    """Пользователь может только занизить сложность, не завысить."""
    claimed_rank = DIFFICULTY_RANK.get(claimed, DIFFICULTY_RANK["medium"])
    calculated_rank = DIFFICULTY_RANK.get(calculated, DIFFICULTY_RANK["medium"])
    return RANK_TO_DIFFICULTY[min(claimed_rank, calculated_rank)]


def step_down(difficulty: str) -> str:
    """Снижает сложность на одну ступень (hard -> medium -> easy -> easy)."""
    rank = DIFFICULTY_RANK.get(difficulty, DIFFICULTY_RANK["medium"])
    return RANK_TO_DIFFICULTY[max(0, rank - 1)]


def difficulty_from_points(point: int) -> str:
    """Определяет текущую условную сложность привычки по её point (обратная операция)."""
    from app.services.points import HABIT_DIFFICULTY_POINTS

    for difficulty, value in HABIT_DIFFICULTY_POINTS.items():
        if value == point:
            return difficulty
    return "medium"
