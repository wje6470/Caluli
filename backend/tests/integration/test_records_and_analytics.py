"""紀錄、儀表板、趨勢與資料隔離整合測試（T109、T110 及 Phase 6–8）。"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.clock import today
from app.core.deps import get_current_user
from app.db.models import FoodNutritionReference, HealthProfile, User, normalize_food_name
from app.db.session import get_db
from app.main import app

PER_100G = {
    "calories_kcal": "187.00",
    "protein_g": "6.20",
    "carbs_g": "26.10",
    "fat_g": "6.50",
}


def item_payload(grams: str = "250") -> dict:
    return {
        "food_name": "滷肉飯",
        "portion_grams": grams,
        "default_portion_grams": "250",
        "per_100g": PER_100G,
        "is_user_modified": False,
    }


@pytest.fixture
def user(db_session: Session) -> User:
    user = User(line_user_id=f"U{uuid.uuid4().hex}", display_name="測試")
    db_session.add(user)
    db_session.flush()
    db_session.add(
        HealthProfile(
            user_id=user.id,
            gender="male",
            age_years=28,
            height_cm=Decimal("175"),
            weight_kg=Decimal("68.5"),
            activity_level="moderate",
            bmr_kcal=Decimal("1643.75"),
            tdee_kcal=Decimal("2000.00"),
            target_protein_g=Decimal("120.0"),
            target_carbs_g=Decimal("220.0"),
            target_fat_g=Decimal("60.0"),
        )
    )
    db_session.flush()
    db_session.refresh(user)
    return user


@pytest.fixture
def other_user(db_session: Session) -> User:
    user = User(line_user_id=f"U{uuid.uuid4().hex}")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def seeded_food(db_session: Session) -> FoodNutritionReference:
    ref = FoodNutritionReference(
        model_label="braised_pork_rice",
        name="滷肉飯",
        name_normalized=normalize_food_name("滷肉飯"),
        calories_kcal_per_100g=Decimal("187.00"),
        protein_g_per_100g=Decimal("6.20"),
        carbs_g_per_100g=Decimal("26.10"),
        fat_g_per_100g=Decimal("6.50"),
        default_portion_grams=Decimal("250.0"),
    )
    db_session.add(ref)
    db_session.flush()
    return ref


@pytest.fixture
def client(db_session: Session, user: User):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    yield httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------
# 儲存與驗算
# --------------------------------------------------------------------------


async def test_create_record_recomputes_nutrients_from_per_100g(client):
    async with client as ac:
        response = await ac.post(
            "/api/v1/meal-records",
            json={"meal_type": "lunch", "items": [item_payload("250")]},
        )

    assert response.status_code == 201
    body = response.json()
    # 187 × 250/100 = 467.50，由後端計算而非採信客戶端。
    assert body["items"][0]["nutrients"]["calories_kcal"] == "467.50"
    assert body["totals"]["calories_kcal"] == "467.50"


async def test_backend_ignores_client_supplied_nutrient_values(client):
    """客戶端只送 per_100g 與份量；換算結果一律後端算（R-09）。"""
    payload = item_payload("375")
    payload["nutrients"] = {"calories_kcal": "1", "protein_g": "1", "carbs_g": "1", "fat_g": "1"}

    async with client as ac:
        response = await ac.post(
            "/api/v1/meal-records", json={"meal_type": "dinner", "items": [payload]}
        )

    # 187 × 3.75 = 701.25
    assert response.json()["items"][0]["nutrients"]["calories_kcal"] == "701.25"


async def test_totals_sum_multiple_items(client):
    async with client as ac:
        response = await ac.post(
            "/api/v1/meal-records",
            json={"meal_type": "lunch", "items": [item_payload("100"), item_payload("200")]},
        )
    assert response.json()["totals"]["calories_kcal"] == "561.00"


async def test_invalid_portion_rejected(client):
    async with client as ac:
        response = await ac.post(
            "/api/v1/meal-records",
            json={"meal_type": "lunch", "items": [item_payload("0")]},
        )
    assert response.status_code == 422


# --------------------------------------------------------------------------
# 儀表板（US3）
# --------------------------------------------------------------------------


async def test_dashboard_empty_day_shows_full_remaining(client):
    async with client as ac:
        response = await ac.get("/api/v1/dashboard")

    body = response.json()
    assert body["consumed"]["calories_kcal"] == "0"
    assert body["remaining"]["calories_kcal"] == "2000.00"
    assert body["over_target"] is False
    assert body["records"] == []


async def test_dashboard_reflects_saved_records(client):
    async with client as ac:
        await ac.post(
            "/api/v1/meal-records", json={"meal_type": "lunch", "items": [item_payload("250")]}
        )
        response = await ac.get("/api/v1/dashboard")

    body = response.json()
    assert body["consumed"]["calories_kcal"] == "467.50"
    assert body["remaining"]["calories_kcal"] == "1532.50"
    assert len(body["records"]) == 1


async def test_dashboard_flags_over_target(client):
    async with client as ac:
        # 2500g → 187 × 25 = 4675 kcal，遠超 2000 目標
        await ac.post(
            "/api/v1/meal-records", json={"meal_type": "dinner", "items": [item_payload("2500")]}
        )
        response = await ac.get("/api/v1/dashboard")

    body = response.json()
    assert body["over_target"] is True
    # 超標時剩餘為負值，讓前端能明確標示而非顯示誤導性的 0。
    assert Decimal(body["remaining"]["calories_kcal"]) < 0


async def test_dashboard_other_date_is_isolated(client):
    yesterday = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    async with client as ac:
        await ac.post(
            "/api/v1/meal-records",
            json={"meal_type": "lunch", "captured_at": yesterday, "items": [item_payload("250")]},
        )
        today_view = await ac.get("/api/v1/dashboard")

    assert today_view.json()["consumed"]["calories_kcal"] == "0"


# --------------------------------------------------------------------------
# 趨勢（US4）
# --------------------------------------------------------------------------


async def test_trends_fills_empty_days_with_zero(client):
    """★ FR-054：沒有紀錄的日期回 0，不略過、不中斷。"""
    async with client as ac:
        await ac.post(
            "/api/v1/meal-records", json={"meal_type": "lunch", "items": [item_payload("250")]}
        )
        response = await ac.get("/api/v1/trends?range_days=7&metric=calories")

    body = response.json()
    assert len(body["points"]) == 7, "必須回傳完整日期序列"
    assert body["points"][-1]["date"] == today().isoformat()
    assert body["points"][-1]["value"] == "467.50"
    # 前 6 天沒有紀錄 → 一律 0
    assert all(p["value"] == "0" for p in body["points"][:6])


async def test_trends_supports_all_metrics(client):
    async with client as ac:
        await ac.post(
            "/api/v1/meal-records", json={"meal_type": "lunch", "items": [item_payload("250")]}
        )
        for metric, expected in [("protein", "15.50"), ("carbs", "65.25"), ("fat", "16.25")]:
            response = await ac.get(f"/api/v1/trends?range_days=7&metric={metric}")
            assert response.json()["points"][-1]["value"] == expected


async def test_trends_with_no_records_returns_all_zero(client):
    async with client as ac:
        response = await ac.get("/api/v1/trends?range_days=30&metric=calories")

    body = response.json()
    assert len(body["points"]) == 30
    assert body["average"] == "0.00"
    assert all(p["value"] == "0" for p in body["points"])


# --------------------------------------------------------------------------
# 維護（US5）
# --------------------------------------------------------------------------


async def test_edit_record_updates_totals(client):
    async with client as ac:
        created = await ac.post(
            "/api/v1/meal-records", json={"meal_type": "lunch", "items": [item_payload("250")]}
        )
        record_id = created.json()["id"]

        updated = await ac.patch(
            f"/api/v1/meal-records/{record_id}",
            json={"meal_type": "lunch", "items": [item_payload("100")]},
        )
        dashboard = await ac.get("/api/v1/dashboard")

    assert updated.json()["totals"]["calories_kcal"] == "187.00"
    assert dashboard.json()["consumed"]["calories_kcal"] == "187.00"


async def test_delete_record_removes_it_from_totals(client):
    async with client as ac:
        created = await ac.post(
            "/api/v1/meal-records", json={"meal_type": "lunch", "items": [item_payload("250")]}
        )
        deleted = await ac.delete(f"/api/v1/meal-records/{created.json()['id']}")
        dashboard = await ac.get("/api/v1/dashboard")

    assert deleted.status_code == 204
    assert dashboard.json()["consumed"]["calories_kcal"] == "0"


async def test_profile_recalculation_does_not_alter_history(client, db_session, user):
    """★ FR-016：重算目標不得改變任何既有紀錄的營養值（快照機制）。"""
    async with client as ac:
        created = await ac.post(
            "/api/v1/meal-records", json={"meal_type": "lunch", "items": [item_payload("250")]}
        )
        before = created.json()["items"][0]["nutrients"]

        # 大幅改變體重 → 目標重算
        await ac.put(
            "/api/v1/me/profile",
            json={
                "gender": "male",
                "age_years": 28,
                "height_cm": "175",
                "weight_kg": "95",
                "activity_level": "high",
            },
        )
        after = await ac.get(f"/api/v1/meal-records?date={today().isoformat()}")

    assert after.json()["records"][0]["items"][0]["nutrients"] == before


async def test_food_reference_deletion_preserves_history(client, db_session, seeded_food):
    """刪除對照表項目不得刪掉使用者的歷史紀錄（ON DELETE SET NULL）。"""
    payload = item_payload("250")
    payload["food_reference_id"] = str(seeded_food.id)

    async with client as ac:
        created = await ac.post(
            "/api/v1/meal-records", json={"meal_type": "lunch", "items": [payload]}
        )
        record_id = created.json()["id"]

        db_session.delete(seeded_food)
        db_session.flush()

        after = await ac.get(f"/api/v1/meal-records?date={today().isoformat()}")

    records = after.json()["records"]
    assert len(records) == 1
    assert records[0]["id"] == record_id
    # 營養值來自快照，不因對照表被刪而消失。
    assert records[0]["items"][0]["nutrients"]["calories_kcal"] == "467.50"
    assert records[0]["items"][0]["food_reference_id"] is None


# --------------------------------------------------------------------------
# ★ 資料隔離（T110、FR-044、SC-009）
# --------------------------------------------------------------------------


async def test_cannot_read_edit_or_delete_another_users_record(
    client, db_session, other_user, user
):
    async with client as ac:
        created = await ac.post(
            "/api/v1/meal-records", json={"meal_type": "lunch", "items": [item_payload("250")]}
        )
        record_id = created.json()["id"]

        # 切換為另一位使用者
        app.dependency_overrides[get_current_user] = lambda: other_user

        read = await ac.get(f"/api/v1/meal-records/{record_id}/photo")
        edit = await ac.patch(
            f"/api/v1/meal-records/{record_id}",
            json={"meal_type": "dinner", "items": [item_payload("100")]},
        )
        delete = await ac.delete(f"/api/v1/meal-records/{record_id}")
        listing = await ac.get(f"/api/v1/meal-records?date={today().isoformat()}")

    # 一律 404 而非 403——不洩漏資源是否存在。
    assert read.status_code == 404
    assert edit.status_code == 404
    assert delete.status_code == 404
    assert listing.json()["records"] == []


async def test_other_users_records_excluded_from_dashboard_and_trends(
    client, db_session, other_user, user
):
    async with client as ac:
        await ac.post(
            "/api/v1/meal-records", json={"meal_type": "lunch", "items": [item_payload("250")]}
        )

        app.dependency_overrides[get_current_user] = lambda: other_user
        dashboard = await ac.get("/api/v1/dashboard")
        trends = await ac.get("/api/v1/trends?range_days=7&metric=calories")

    assert dashboard.json()["consumed"]["calories_kcal"] == "0"
    assert all(p["value"] == "0" for p in trends.json()["points"])
