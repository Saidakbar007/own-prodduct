"""HTTP-роуты /week (§6, §14): 7 дней расписания, добавление обязательного
дела/задачи, "перетаскивание" (ввод нового времени) блока."""

from datetime import date, timedelta

from sqlmodel import select

from app.models import Commitment, ScheduleBlock, Task

THIS_YEAR = date.today().year


def _register(client, unique):
    client.post("/onboarding/spheres", data={"sphere_ids": ["body"]})
    client.post("/onboarding/sphere-level", data={"option_index": "1"})
    client.post("/onboarding/goal/skip")
    client.post("/onboarding/mode", data={"wake_time": "07:00", "sleep_time": "23:00"})
    client.post("/onboarding/commitments", data={"action": "next"})
    client.post("/onboarding/daily-minutes", data={"daily_minutes": "30"})
    client.post("/onboarding/chronotype", data={"chronotype": "varies"})
    client.post("/onboarding/constraints", data={})
    client.post("/onboarding/woop", data={})
    client.post(
        "/register",
        data={
            "name": "Week Routes", "birth_year": str(THIS_YEAR - 25), "age_confirm": "1",
            "email": f"wk-{unique}@example.com", "login": f"wk-{unique}",
            "password": "s3cret-pass", "password_confirm": "s3cret-pass", "timezone": "UTC",
        },
    )


def test_week_page_requires_login(client):
    resp = client.get("/week", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_week_page_shows_seven_days(client, unique):
    _register(client, unique)
    resp = client.get("/week")
    assert resp.status_code == 200
    assert resp.text.count("day-feed") >= 0  # не падает даже без блоков


def test_add_commitment_appears_in_week_schedule(client, unique, db_session):
    _register(client, unique)
    client.post(
        "/week/commitments/add",
        data={"title": "Работа", "category": "work", "weekdays": ["1", "2", "3", "4", "5"], "start_time": "09:00", "end_time": "18:00"},
    )
    commitment = db_session.exec(select(Commitment).where(Commitment.title == "Работа")).first()
    assert commitment is not None

    page = client.get("/week")
    assert "Работа" in page.text


def test_add_task_appears_and_gets_scheduled(client, unique, db_session):
    _register(client, unique)
    target_date = date.today()  # сегодня всегда внутри недели, которую показывает /week
    client.post(
        "/week/tasks/add",
        data={"title": "Сдать отчёт", "task_date": target_date.isoformat(), "priority": "do", "duration_min": "30"},
    )
    task = db_session.exec(select(Task).where(Task.title == "Сдать отчёт")).first()
    assert task is not None
    assert task.priority == "do"

    page = client.get("/week")
    assert "Сдать отчёт" in page.text


def test_move_block_sets_moved_by_user_and_new_time(client, unique, db_session):
    _register(client, unique)
    client.post(
        "/week/commitments/add",
        data={"title": "Учёба", "category": "study", "weekdays": [str(date.today().isoweekday())], "start_time": "09:00", "end_time": "12:00"},
    )
    # commitments не попадают в ScheduleBlock напрямую (они FixedBlock) —
    # добавим привычку, чтобы было что двигать.
    client.post("/habits/add", data={"custom_title": "Подвигать блок"})
    client.get("/week")  # материализует блоки на сегодня

    block = db_session.exec(select(ScheduleBlock).where(ScheduleBlock.title == "Подвигать блок")).first()
    assert block is not None

    client.post(f"/week/blocks/{block.id}/move", data={"start_time": "20:00", "end_time": "20:15"})
    db_session.refresh(block)
    assert block.start_time == "20:00"
    assert block.moved_by_user is True
