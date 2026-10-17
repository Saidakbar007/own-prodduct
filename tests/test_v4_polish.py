"""Тесты v4: лендинг, демо-вход в один клик, 404-страница, PWA-файлы."""

from tests.conftest import register_user


def test_guest_sees_landing_without_app_nav(client):
    home = client.get("/")
    assert home.status_code == 200
    assert "Попробовать демо" in home.text
    assert "Как это работает" in home.text
    # разделов приложения в гостевой навигации нет
    assert 'href="/habits"' not in home.text
    assert 'href="/goals"' not in home.text


def test_try_demo_logs_in_as_demo_user(client, session):
    from sqlmodel import select

    from app.auth import hash_password
    from app.models import Level, Registration, User

    # сам создаём demo-пользователя, как это делает seed.py
    session.add(Registration(name="Demo", mail="demo@example.com", login="demo", password=hash_password("demo1234")))
    session.commit()
    demo_user = User(mail="demo@example.com", login="demo")
    session.add(demo_user)
    session.commit()
    session.refresh(demo_user)
    session.add(Level(uid=demo_user.id, point=0, name="Новичок"))
    session.commit()

    resp = client.get("/try-demo", follow_redirects=False)
    assert resp.status_code == 303

    home = client.get("/")
    assert "demo" in home.text


def test_try_demo_without_seeded_demo_user_does_not_crash(client):
    resp = client.get("/try-demo", follow_redirects=False)
    assert resp.status_code == 303  # просто ведёт на главную, без демо-сессии


def test_404_page_for_unknown_route(client):
    resp = client.get("/this-route-does-not-exist")
    assert resp.status_code == 404
    assert "не найдена" in resp.text.lower() or "не существует" in resp.text.lower()


def test_logged_in_nav_hides_guest_links(client):
    register_user(client, login="petra", mail="petra@example.com")
    home = client.get("/")
    assert 'href="/register"' not in home.text


def test_base_html_has_dark_mode_bootstrap_script(client):
    home = client.get("/")
    assert "__applyTheme" in home.text
    assert "darkMode" in home.text


def test_manifest_and_service_worker_are_served(client):
    manifest = client.get("/static/manifest.json")
    assert manifest.status_code == 200
    assert "short_name" in manifest.text

    sw = client.get("/static/sw.js")
    assert sw.status_code == 200
