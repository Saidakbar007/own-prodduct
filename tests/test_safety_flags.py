"""Безопасность (NEWLIFE_1_0_CONTENT.md §6 «Предупреждения и красные
флаги»): диагноз/ограничения, беременность, сигналы РПП. Доп. задача, см.
docs/decisions/DECISIONS.md."""

from datetime import date

from sqlmodel import select

from app.models import Profile, Season, SeasonDay, User
from app.seasons.engine import has_eating_disorder_signal

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Безопасность Тест",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"safety-{unique}@example.com",
        "login": f"safety-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------- engine helper


def test_eating_disorder_signal_true_for_low_bmi_without_self_report():
    assert has_eating_disorder_signal(50, 180, None, self_reported=False) is True


def test_eating_disorder_signal_true_for_self_report_with_normal_bmi():
    assert has_eating_disorder_signal(75, 180, None, self_reported=True) is True


def test_eating_disorder_signal_false_when_neither():
    assert has_eating_disorder_signal(75, 180, 70, self_reported=False) is False


def test_eating_disorder_signal_true_for_low_target_bmi():
    assert has_eating_disorder_signal(75, 180, 55, self_reported=False) is True


# --------------------------------------------------------- /onboarding/health


def test_pregnancy_blocks_fat_loss_safe(client, unique):
    client.post("/onboarding/goal", data={"template_id": "fat_loss_safe"})
    resp = client.post(
        "/onboarding/health",
        data={"height_cm": "170", "weight_kg": "65", "birth_year": str(THIS_YEAR - 22), "is_pregnant": "1"},
    )
    assert resp.status_code == 200
    assert "недоступна" in resp.text or "не для тебя" not in resp.text  # не bmi-текст, а pregnancy-текст
    assert "беременн" in resp.text.lower() or "homilad" in resp.text.lower()


def test_pregnancy_blocks_muscle_gain_too(client, unique):
    client.post("/onboarding/goal", data={"template_id": "muscle_gain"})
    resp = client.post(
        "/onboarding/health",
        data={"height_cm": "170", "weight_kg": "65", "birth_year": str(THIS_YEAR - 22), "is_pregnant": "1"},
    )
    assert resp.status_code == 200
    assert "беременн" in resp.text.lower()


def test_eating_signal_self_report_blocks_fat_loss_safe_with_normal_bmi(client, unique):
    client.post("/onboarding/goal", data={"template_id": "fat_loss_safe"})
    resp = client.post(
        "/onboarding/health",
        data={
            "height_cm": "170",
            "weight_kg": "65",  # нормальный ИМТ ~22.5, блокирует только самоотчёт
            "birth_year": str(THIS_YEAR - 22),
            "disordered_eating_signal": "1",
        },
    )
    assert resp.status_code == 200
    assert "специалист" in resp.text.lower() or "mutaxassis" in resp.text.lower()


def test_no_safety_flags_proceeds_normally(client, unique):
    client.post("/onboarding/goal", data={"template_id": "fat_loss_safe"})
    resp = client.post(
        "/onboarding/health",
        data={"height_cm": "170", "weight_kg": "80", "birth_year": str(THIS_YEAR - 22)},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "недоступна" not in resp.text
    assert "специалист" not in resp.text.lower()


def test_safety_flags_persist_to_profile_at_registration(client, unique, db_session):
    client.post("/onboarding/goal", data={"template_id": "muscle_gain"})
    client.post(
        "/onboarding/health",
        data={
            "height_cm": "180",
            "weight_kg": "75",
            "birth_year": str(THIS_YEAR - 25),
            "has_medical_diagnosis": "1",
        },
    )
    client.post("/onboarding/baseline", data={"value": "40"})
    client.post("/onboarding/schedule", data={"length_days": "90"})
    client.get("/onboarding/trailer")
    reg = client.post("/register", data=_register_payload(unique), follow_redirects=True)
    assert reg.status_code == 200

    user = db_session.exec(select(User).where(User.login == f"safety-{unique}")).first()
    profile = db_session.exec(select(Profile).where(Profile.uid == user.id)).first()
    assert profile.has_medical_diagnosis is True
    assert profile.is_pregnant is None or profile.is_pregnant is False


# --------------------------------------------------------- /today minimal_only


def test_today_shows_only_minimal_action_when_diagnosis_flagged(client, unique, db_session):
    client.post("/onboarding/goal", data={"template_id": "sitting_breaks"})
    client.post("/onboarding/baseline", data={"value": "2"})
    client.post("/onboarding/schedule", data={"length_days": "30"})
    client.get("/onboarding/trailer")
    reg = client.post("/register", data=_register_payload(unique), follow_redirects=True)
    assert reg.status_code == 200

    user = db_session.exec(select(User).where(User.login == f"safety-{unique}")).first()
    profile = db_session.exec(select(Profile).where(Profile.uid == user.id)).first()
    profile.has_medical_diagnosis = True
    db_session.add(profile)

    season = db_session.exec(select(Season).where(Season.uid == user.id).order_by(Season.id.desc())).first()
    day = db_session.exec(
        select(SeasonDay).where(SeasonDay.season_id == season.id, SeasonDay.day_number == 1)
    ).first()
    day.kind = "train"
    day.status = "planned"
    db_session.add(day)
    db_session.commit()

    resp = client.get("/today")
    assert resp.status_code == 200
    assert "today-done-form" not in resp.text
    assert "today-minimal-form" in resp.text


# --------------------------------------------------------- catalog filtering


def test_goal_catalog_hides_fat_loss_and_muscle_gain_for_pregnant_profile(client, unique, db_session):
    client.post("/onboarding/goal", data={"template_id": "sitting_breaks"})
    client.post("/onboarding/baseline", data={"value": "2"})
    client.post("/onboarding/schedule", data={"length_days": "30"})
    client.get("/onboarding/trailer")
    reg = client.post("/register", data=_register_payload(unique), follow_redirects=True)
    assert reg.status_code == 200

    user = db_session.exec(select(User).where(User.login == f"safety-{unique}")).first()
    profile = db_session.exec(select(Profile).where(Profile.uid == user.id)).first()
    profile.is_pregnant = True
    db_session.add(profile)
    db_session.commit()

    resp = client.get("/onboarding/goal")
    assert resp.status_code == 200
    assert 'template_id" value="fat_loss_safe"' not in resp.text
    assert 'template_id" value="muscle_gain"' not in resp.text
