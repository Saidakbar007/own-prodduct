"""E2e: демо-данные v6b — питомец вылупился, идёт бой с боссом недели."""


def test_demo_pet_hatched(demo_page, e2e_server):
    demo_page.goto(f"{e2e_server}/hero")
    demo_page.wait_for_load_state("networkidle")
    content = demo_page.content()
    assert "Лис" in content
    assert "яйцо" not in content.lower() or "вылупится" not in content.lower()


def test_demo_boss_fight_in_progress(demo_page, e2e_server):
    demo_page.goto(f"{e2e_server}/boss")
    demo_page.wait_for_load_state("networkidle")
    content = demo_page.content()
    assert "HP" in content
    assert "Лента ударов" in content
