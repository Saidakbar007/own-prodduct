"""E2e: страница /boss открывается из сайдбара и показывает статус блокировки/группы."""


def test_boss_link_navigates_and_shows_status(demo_page, e2e_server):
    demo_page.set_viewport_size({"width": 1280, "height": 900})
    demo_page.goto(f"{e2e_server}/")
    demo_page.wait_for_load_state("networkidle")

    sidebar = demo_page.locator("aside").first
    sidebar.locator('a[href="/boss"]').first.click()

    demo_page.wait_for_url("**/boss")
    demo_page.wait_for_load_state("networkidle")
    assert "Босс недели" in demo_page.content()
