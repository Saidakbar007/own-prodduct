"""/admin/analytics — алиас /admin; воронка/когорты/популярность сфер
исключают demo и ADMIN_LOGINS (доп. задача, см. docs/decisions/
DECISIONS.md → «Этап "Доделай" + guide + wger»)."""

from datetime import date

from app.services import admin_stats

THIS_YEAR = date.today().year


def _register(client, login):
    return client.post(
        "/register",
        data={
            "name": "Аналитика Тест",
            "birth_year": str(THIS_YEAR - 25),
            "age_confirm": "1",
            "email": f"{login}@example.com",
            "login": login,
            "password": "s3cret-pass",
            "password_confirm": "s3cret-pass",
            "timezone": "UTC",
        },
        follow_redirects=True,
    )


def test_admin_analytics_is_an_alias_of_admin(client, monkeypatch, unique):
    login = f"aadmin-{unique}"
    monkeypatch.setenv("ADMIN_LOGINS", login)
    _register(client, login)

    dashboard = client.get("/admin")
    analytics = client.get("/admin/analytics")
    assert dashboard.status_code == analytics.status_code == 200
    assert "Воронка" in analytics.text


def _insert_signup_event(db_session, login: str, unique: str) -> None:
    from app.models import Event, User

    user = User(
        name="X", login=login, email=f"{login}-{unique}@example.com",
        password_hash="x", timezone="UTC", birth_year=THIS_YEAR - 25,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(Event(event_type="signup", uid=user.id))
    db_session.commit()


def test_demo_login_excluded_from_funnel_counts(monkeypatch, unique, db_session):
    monkeypatch.setenv("ADMIN_LOGINS", "")
    before = admin_stats.funnel_counts(db_session)["signup"]

    _insert_signup_event(db_session, "demo", unique)

    after = admin_stats.funnel_counts(db_session)["signup"]
    assert after == before  # "demo" не поднимает счётчик


def test_admin_login_excluded_from_funnel_counts(monkeypatch, unique, db_session):
    login = f"excluded-{unique}"
    monkeypatch.setenv("ADMIN_LOGINS", login)
    before = admin_stats.funnel_counts(db_session)["signup"]

    _insert_signup_event(db_session, login, unique)

    after = admin_stats.funnel_counts(db_session)["signup"]
    assert after == before


def test_sphere_popularity_excludes_admin_login(client, monkeypatch, unique, db_session):
    login = f"sphereadmin-{unique}"
    before = dict(admin_stats.sphere_popularity(db_session))

    monkeypatch.setenv("ADMIN_LOGINS", login)
    client.post("/onboarding/spheres", data={"sphere_ids": ["values"]})
    reg = _register(client, login)
    assert reg.status_code == 200

    after = dict(admin_stats.sphere_popularity(db_session))
    # Исключённый админ-логин выбрал "values" — счётчик не должен вырасти.
    assert after.get("values", 0) == before.get("values", 0)
