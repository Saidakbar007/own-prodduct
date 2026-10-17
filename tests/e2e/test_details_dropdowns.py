"""E2E: нативные <details>/<summary> раскрывающиеся блоки (добавление цели/программ) кликаются."""


def test_add_goal_details_expands_and_submits(demo_page, e2e_server):
    demo_page.goto(f"{e2e_server}/goals")
    demo_page.wait_for_load_state("networkidle")

    summary = demo_page.locator("summary", has_text="добавить цель").first
    summary.click()

    form_input = demo_page.locator('form[action*="/child"] input[name="name"]').first
    form_input.wait_for(state="visible", timeout=3000)
    form_input.fill("E2E цель через details")
    demo_page.locator('form[action*="/child"] button[type="submit"]').first.click()
    demo_page.wait_for_load_state("networkidle")

    assert "E2E цель через details" in demo_page.content()


def test_add_training_program_details_expands_and_submits(demo_page, e2e_server):
    demo_page.goto(f"{e2e_server}/goals")
    demo_page.wait_for_load_state("networkidle")

    goal_link = demo_page.locator('a[href^="/goals/"]').first
    goal_link.click()
    demo_page.wait_for_load_state("networkidle")

    training_summary = demo_page.locator("details", has=demo_page.locator('form[action*="/training"]')).locator("summary").first
    training_summary.click()

    name_input = demo_page.locator('form[action*="/training"] input[name="name"]').first
    name_input.wait_for(state="visible", timeout=3000)
    name_input.fill("E2E тренировка")
    demo_page.locator('form[action*="/training"] button[type="submit"]').first.click()
    demo_page.wait_for_load_state("networkidle")

    assert "E2E тренировка" in demo_page.content()
