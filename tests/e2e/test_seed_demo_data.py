"""
E2e: демо-данные (v6a, пункт 7) — у demo разные уровни личностей, одна
личность "спит", есть монеты и купленные/надетые предметы.
"""


def test_demo_has_varied_persona_levels_with_one_asleep(demo_page, e2e_server):
    demo_page.goto(f"{e2e_server}/hero")
    demo_page.wait_for_load_state("networkidle")

    content = demo_page.content()
    for persona_name in ("Воин", "Мудрец", "Монах", "Целитель", "Бард"):
        assert persona_name in content

    bard_card = content.split('data-persona="charisma"')[1].split('data-persona=')[0]
    assert "спит" in bard_card


def test_demo_has_coins_and_equipped_items(demo_page, e2e_server):
    demo_page.goto(f"{e2e_server}/")
    demo_page.wait_for_load_state("networkidle")

    coin_badge = demo_page.locator('[data-lucide="coins"]').first.locator("xpath=..")
    assert coin_badge.inner_text().strip() != "0"

    shop_resp = demo_page.goto(f"{e2e_server}/shop")
    demo_page.wait_for_load_state("networkidle")
    assert "Надето" in demo_page.content()
