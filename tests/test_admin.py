"""Админка (§14, Фаза 4) — доступ по ADMIN_LOGINS, дашборд, галерея, песочница."""

from datetime import date

from app.services import admin_stats

THIS_YEAR = date.today().year


def _register(client, login, admin_logins_env=None, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setenv("ADMIN_LOGINS", admin_logins_env or "")
    return client.post(
        "/register",
        data={
            "name": "Админ Тестов",
            "birth_year": str(THIS_YEAR - 25),
            "age_confirm": "1",
            "email": f"{login}@example.com",
            "login": login,
            "password": "s3cret-pass",
            "password_confirm": "s3cret-pass",
            "timezone": "UTC",
        },
    )


def test_admin_routes_404_for_non_admin(client, monkeypatch, unique):
    monkeypatch.setenv("ADMIN_LOGINS", f"someoneelse-{unique}")
    _register(client, f"regular-{unique}")
    assert client.get("/admin").status_code == 404
    assert client.get("/admin/gallery").status_code == 404
    assert client.get("/admin/sandbox").status_code == 404


def test_admin_routes_404_for_guest(client):
    assert client.get("/admin").status_code == 404


def test_admin_dashboard_accessible_for_admin_login(client, monkeypatch, unique):
    login = f"admin-{unique}"
    monkeypatch.setenv("ADMIN_LOGINS", f"someone,{login},another")
    _register(client, login)

    assert client.get("/admin").status_code == 200
    gallery = client.get("/admin/gallery")
    assert gallery.status_code == 200
    assert "run_5k" in gallery.text
    assert client.get("/admin/sandbox").status_code == 200


def test_sandbox_full_flow(client, monkeypatch, unique):
    login = f"sandbox-{unique}"
    monkeypatch.setenv("ADMIN_LOGINS", login)
    _register(client, login)

    create_resp = client.post(
        "/admin/sandbox/create",
        data={"template_id": "pushups_50", "length_days": "30", "baseline_value": "5", "days_ago": "12"},
        follow_redirects=True,
    )
    assert create_resp.status_code == 200
    assert "pushups_50" not in create_resp.text  # должен показать title, не id
    assert "1." in create_resp.text  # дни построены сразу (build_all_days)

    season_id = create_resp.url.path.rstrip("/").split("/")[-1]

    mark_resp = client.post(
        f"/admin/sandbox/{season_id}/mark",
        data={"day_number": "1", "status": "done"},
        follow_redirects=True,
    )
    assert mark_resp.status_code == 200

    measure_resp = client.post(
        f"/admin/sandbox/{season_id}/measure",
        data={"day_number": "1", "value": "12"},
        follow_redirects=True,
    )
    assert measure_resp.status_code == 200

    episode_resp = client.post(
        f"/admin/sandbox/{season_id}/episode",
        data={"week_number": "1"},
        follow_redirects=True,
    )
    assert episode_resp.status_code == 200

    finish_resp = client.post(f"/admin/sandbox/{season_id}/finish", follow_redirects=True)
    assert finish_resp.status_code == 200
    assert "Reveal" in finish_resp.text or "позади" in finish_resp.text


def test_sandbox_rejects_other_users_season(client, monkeypatch, unique):
    login_a = f"sbx-a-{unique}"
    login_b = f"sbx-b-{unique}"

    monkeypatch.setenv("ADMIN_LOGINS", f"{login_a},{login_b}")
    _register(client, login_a)
    create_resp = client.post(
        "/admin/sandbox/create",
        data={"template_id": "run_5k", "length_days": "60", "baseline_value": "5", "days_ago": "5"},
        follow_redirects=True,
    )
    season_id = create_resp.url.path.rstrip("/").split("/")[-1]
    client.get("/logout")

    from fastapi.testclient import TestClient

    import app.main

    other_client = TestClient(app.main.app)
    _register(other_client, login_b)
    resp = other_client.get(f"/admin/sandbox/{season_id}")
    assert resp.status_code == 404


def test_funnel_counts_returns_known_keys(db_session):
    counts = admin_stats.funnel_counts(db_session)
    assert set(counts.keys()) == set(admin_stats.FUNNEL_STEPS)
    assert all(isinstance(v, int) for v in counts.values())


def test_retention_for_cohort_with_no_signups_returns_none_rate(db_session):
    result = admin_stats.retention_for_cohort(db_session, date(2000, 1, 1), 7)
    assert result["cohort_size"] == 0
    assert result["rate"] is None


def test_reveal_completion_rate_none_when_no_seasons_started(db_session):
    # не проверяем точное значение (другие тесты могли уже что-то насоздавать),
    # только то, что функция не падает и возвращает долю либо None
    rate = admin_stats.reveal_completion_rate(db_session)
    assert rate is None or 0.0 <= rate <= 1.0
