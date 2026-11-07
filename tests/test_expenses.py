"""Трекер трат (категории кнопками + сумма + итог месяца) — доп. задача,
см. app/services/expenses.py и docs/decisions/DECISIONS.md → «Этап
"Доделай" + guide + wger»."""

from datetime import date

from app.models import User
from app.services.expenses import CATEGORIES, month_totals_by_category

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Траты Тест",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"ex-{unique}@example.com",
        "login": f"ex-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


def _register(client, unique):
    client.post("/onboarding/spheres", data={"sphere_ids": ["body"]})
    client.post("/onboarding/sphere-level", data={"option_index": "2"})
    return client.post("/register", data=_register_payload(unique), follow_redirects=True)


def test_expenses_page_renders_for_logged_in_user(client, unique):
    _register(client, unique)
    resp = client.get("/expenses")
    assert resp.status_code == 200
    assert "Еда" in resp.text


def test_logging_an_expense_adds_to_month_total(client, unique, db_session):
    from sqlmodel import select

    _register(client, unique)
    user = db_session.exec(select(User).where(User.login == f"ex-{unique}")).first()

    resp = client.post("/expenses/log", data={"category": "food", "amount": "25000"}, follow_redirects=True)
    assert resp.status_code == 200

    totals = month_totals_by_category(db_session, user.id, date.today())
    food_total = next(t.total for t in totals if t.category == "food")
    assert food_total == 25000.0


def test_month_totals_covers_all_categories_even_with_no_entries(db_session):
    user = User(
        name="Y", login="ex-empty", email="ex-empty@example.com",
        password_hash="x", timezone="UTC", birth_year=THIS_YEAR - 25,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    totals = month_totals_by_category(db_session, user.id, date.today())
    assert [t.category for t in totals] == CATEGORIES
    assert all(t.total == 0.0 for t in totals)


def test_season_detail_links_to_expenses_for_expense_tracking_goal(client, unique):
    client.post("/onboarding/goal", data={"template_id": "expense_tracking"})
    client.post("/onboarding/baseline", data={"value": "0"})
    client.post("/onboarding/schedule", data={"length_days": "30"})
    client.get("/onboarding/trailer")
    reg = client.post(
        "/register",
        data=_register_payload(unique, login=f"ex2-{unique}", email=f"ex2-{unique}@example.com"),
        follow_redirects=True,
    )
    assert reg.status_code == 200

    season_page = client.get("/season", follow_redirects=True)
    assert season_page.status_code == 200
    assert "/expenses" in season_page.text


def test_invalid_category_is_rejected_silently(client, unique, db_session):
    from sqlmodel import select

    _register(client, unique)
    user = db_session.exec(select(User).where(User.login == f"ex-{unique}")).first()

    client.post("/expenses/log", data={"category": "not-a-real-category", "amount": "5000"}, follow_redirects=True)
    totals = month_totals_by_category(db_session, user.id, date.today())
    assert all(t.total == 0.0 for t in totals)
