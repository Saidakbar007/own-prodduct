"""E2e: карточка питомца видна на /hero и на главной."""


def test_pet_card_visible_on_hero_and_home(demo_page, e2e_server):
    demo_page.goto(f"{e2e_server}/hero")
    demo_page.wait_for_load_state("networkidle")
    assert "Питомец" in demo_page.content()

    demo_page.goto(f"{e2e_server}/")
    demo_page.wait_for_load_state("networkidle")
    assert "Питомец" in demo_page.content()
