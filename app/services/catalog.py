"""
Каталог типовых привычек (~30): готовые сфера+сложность, чтобы не доверять
пользователю ставить себе лёгкие привычки с завышенной сложностью.
"""

CATALOG = [
    # Здоровье
    {"code": "water", "name": "Пить воду", "sphere": "health", "difficulty": "easy"},
    {"code": "sleep8", "name": "Спать 8 часов", "sphere": "health", "difficulty": "medium"},
    {"code": "no_sugar", "name": "Без сахара", "sphere": "health", "difficulty": "medium"},
    {"code": "vitamins", "name": "Принимать витамины", "sphere": "health", "difficulty": "easy"},
    {"code": "no_smoking", "name": "Не курить", "sphere": "health", "difficulty": "hard"},
    {"code": "no_alcohol", "name": "Без алкоголя", "sphere": "health", "difficulty": "hard"},
    {"code": "veggies", "name": "Есть овощи каждый день", "sphere": "health", "difficulty": "easy"},
    {"code": "early_sleep", "name": "Ложиться спать до 23:00", "sphere": "health", "difficulty": "medium"},

    # Сила
    {"code": "morning_exercise", "name": "Зарядка по утрам", "sphere": "strength", "difficulty": "easy"},
    {"code": "gym", "name": "Тренировка в зале", "sphere": "strength", "difficulty": "hard"},
    {"code": "run5k", "name": "Пробежать 5 км", "sphere": "strength", "difficulty": "medium"},
    {"code": "pushups", "name": "Отжимания", "sphere": "strength", "difficulty": "easy"},
    {"code": "stretching", "name": "Растяжка 10 минут", "sphere": "strength", "difficulty": "easy"},
    {"code": "steps10k", "name": "10000 шагов в день", "sphere": "strength", "difficulty": "medium"},
    {"code": "cold_shower", "name": "Холодный душ", "sphere": "strength", "difficulty": "hard"},

    # Интеллект
    {"code": "reading20", "name": "Читать 20 минут", "sphere": "intellect", "difficulty": "medium"},
    {"code": "language", "name": "Учить иностранный язык", "sphere": "intellect", "difficulty": "medium"},
    {"code": "online_course", "name": "Урок онлайн-курса", "sphere": "intellect", "difficulty": "medium"},
    {"code": "coding", "name": "Писать код", "sphere": "intellect", "difficulty": "hard"},
    {"code": "journaling", "name": "Вести дневник", "sphere": "intellect", "difficulty": "easy"},
    {"code": "puzzle", "name": "Решать головоломки/задачи", "sphere": "intellect", "difficulty": "easy"},

    # Дисциплина
    {"code": "no_social_media", "name": "Без соцсетей после 22:00", "sphere": "discipline", "difficulty": "medium"},
    {"code": "wake_early", "name": "Вставать в 6 утра", "sphere": "discipline", "difficulty": "hard"},
    {"code": "clean_desk", "name": "Убирать рабочее место", "sphere": "discipline", "difficulty": "easy"},
    {"code": "no_phone_morning", "name": "Не брать телефон первый час после пробуждения", "sphere": "discipline", "difficulty": "medium"},
    {"code": "meditation", "name": "Медитация 10 минут", "sphere": "discipline", "difficulty": "easy"},
    {"code": "budget_tracking", "name": "Записывать расходы", "sphere": "discipline", "difficulty": "easy"},
    {"code": "no_procrastination", "name": "Сделать самую сложную задачу дня первой", "sphere": "discipline", "difficulty": "hard"},

    # Харизма
    {"code": "call_friend", "name": "Позвонить другу или родным", "sphere": "charisma", "difficulty": "easy"},
    {"code": "compliment", "name": "Сказать кому-то комплимент", "sphere": "charisma", "difficulty": "easy"},
    {"code": "new_contact", "name": "Познакомиться с новым человеком", "sphere": "charisma", "difficulty": "hard"},
    {"code": "public_speaking", "name": "Практика публичных выступлений", "sphere": "charisma", "difficulty": "hard"},
]


def find_by_code(code: str) -> dict | None:
    return next((item for item in CATALOG if item["code"] == code), None)
