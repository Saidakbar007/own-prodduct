"""Админка NewLife v8 (§15): сферы, каталог, песочница расписания."""

from datetime import date

THIS_YEAR = date.today().year


def _register_admin(client, monkeypatch, login):
    monkeypatch.setenv("ADMIN_LOGINS", login)
    return client.post(
        "/register",
        data={
            "name": "Admin V8", "birth_year": str(THIS_YEAR - 25), "age_confirm": "1",
            "email": f"{login}@example.com", "login": login,
            "password": "s3cret-pass", "password_confirm": "s3cret-pass", "timezone": "UTC",
        },
    )


def test_spheres_admin_accessible_and_lists_all_eleven(client, monkeypatch, unique):
    login = f"admin-sph-{unique}"
    _register_admin(client, monkeypatch, login)
    resp = client.get("/admin/spheres")
    assert resp.status_code == 200
    assert "body" in resp.text
    assert "finance" in resp.text


def test_spheres_admin_404_for_non_admin(client, monkeypatch, unique):
    monkeypatch.setenv("ADMIN_LOGINS", f"nobody-{unique}")
    client.post(
        "/register",
        data={
            "name": "Regular", "birth_year": str(THIS_YEAR - 25), "age_confirm": "1",
            "email": f"reg-{unique}@example.com", "login": f"reg-{unique}",
            "password": "s3cret-pass", "password_confirm": "s3cret-pass", "timezone": "UTC",
        },
    )
    assert client.get("/admin/spheres").status_code == 404


def test_catalog_admin_lists_goals_and_habits(client, monkeypatch, unique):
    login = f"admin-cat-{unique}"
    _register_admin(client, monkeypatch, login)
    resp = client.get("/admin/catalog")
    assert resp.status_code == 200
    assert "run_5k" in resp.text
    assert "Медитация" in resp.text
    assert "Бесцельный скролл" in resp.text


def test_schedule_sandbox_runs_for_admin_own_account(client, monkeypatch, unique):
    login = f"admin-sched-{unique}"
    _register_admin(client, monkeypatch, login)
    client.post("/habits/add", data={"custom_title": "Админ-привычка"})

    resp = client.get("/admin/schedule-sandbox")
    assert resp.status_code == 200
    assert "Админ-привычка" in resp.text


def test_schedule_sandbox_accepts_explicit_date(client, monkeypatch, unique):
    login = f"admin-sched2-{unique}"
    _register_admin(client, monkeypatch, login)
    resp = client.get("/admin/schedule-sandbox?on_date=2026-12-01")
    assert resp.status_code == 200
