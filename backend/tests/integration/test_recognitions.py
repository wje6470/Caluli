"""辨識端點整合測試（tasks.md T047）。

涵蓋 quickstart.md V3〜V5 的後端部分：成功、空結果、三類錯誤、重試、
上傳驗證與資料隔離。需要 Docker（testcontainers）；不可用時自動 skip。
"""

import uuid
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.models import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    FoodNutritionReference,
    RecognitionJob,
    User,
    normalize_food_name,
)
from app.db.session import get_db
from app.main import app
from app.services.photo_storage import FileSystemPhotoStorage, get_photo_storage

PHOTO = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
EMPTY_RESPONSE = {"items": [], "message": "沒有偵測到食物，請換一張再試試"}
NORMAL_RESPONSE = {
    "items": [
        {
            "label": "braised_pork_rice",
            "confidence": 0.93,
            "bbox": {"x": 1, "y": 2, "width": 3, "height": 4},
            "candidates": [
                {"label": "braised_pork_rice", "confidence": 0.93},
                {"label": "white_rice", "confidence": 0.04},
            ],
        }
    ],
    "message": None,
}


@pytest.fixture
def seeded_foods(db_session: Session) -> None:
    for label, name, cal, pro, carb, fat, portion in [
        ("braised_pork_rice", "滷肉飯", "187.00", "6.20", "26.10", "6.50", "250.0"),
        ("white_rice", "白飯", "130.00", "2.70", "28.20", "0.30", "200.0"),
    ]:
        db_session.add(
            FoodNutritionReference(
                model_label=label,
                name=name,
                name_normalized=normalize_food_name(name),
                calories_kcal_per_100g=Decimal(cal),
                protein_g_per_100g=Decimal(pro),
                carbs_g_per_100g=Decimal(carb),
                fat_g_per_100g=Decimal(fat),
                default_portion_grams=Decimal(portion),
            )
        )
    db_session.flush()


@pytest.fixture
def user(db_session: Session) -> User:
    user = User(line_user_id=f"U{uuid.uuid4().hex}", display_name="測試使用者")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def other_user(db_session: Session) -> User:
    user = User(line_user_id=f"U{uuid.uuid4().hex}", display_name="另一位使用者")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def photo_root(tmp_path: Path):
    storage = FileSystemPhotoStorage(tmp_path)
    app.dependency_overrides[get_photo_storage] = lambda: storage
    yield storage
    app.dependency_overrides.pop(get_photo_storage, None)


@pytest.fixture
def client(db_session: Session, user: User, tmp_path: Path, monkeypatch):
    """以 db_session 與登入使用者覆寫依賴，並把照片寫入暫存目錄。"""
    # 強制走檔案系統實作：supabase_url 留空即回退到 FileSystemPhotoStorage。
    monkeypatch.setattr(
        "app.services.photo_storage.get_settings",
        lambda: type(
            "S",
            (),
            {
                "photo_storage_root": tmp_path,
                "supabase_url": "",
                "supabase_service_key": "",
            },
        )(),
    )
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    transport = httpx.ASGITransport(app=app)
    yield httpx.AsyncClient(transport=transport, base_url="http://test")
    app.dependency_overrides.clear()


@pytest.fixture
def upstream(monkeypatch):
    """控制辨識服務的回應。"""

    def install(handler):
        transport = httpx.MockTransport(handler)

        class Patched(httpx.AsyncClient):
            def __init__(self, *args, **kwargs):
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        monkeypatch.setattr("app.services.recognition_client.httpx.AsyncClient", Patched)

    return install


def upload(content: bytes = PHOTO, content_type: str = "image/jpeg"):
    return {"photo": ("meal.jpg", content, content_type)}


# --------------------------------------------------------------------------
# 成功路徑
# --------------------------------------------------------------------------


async def test_successful_recognition_returns_items_with_per_100g(
    client, upstream, seeded_foods, db_session
):
    """★ per_100g 必須出現在回應中——前端靠它做份量即時換算（R-09）。"""
    upstream(lambda request: httpx.Response(200, json=NORMAL_RESPONSE))

    async with client as ac:
        response = await ac.post("/api/v1/recognitions", files=upload())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == STATUS_COMPLETED
    assert len(body["items"]) == 1

    item = body["items"][0]
    assert item["name"] == "滷肉飯"
    assert item["nutrition_available"] is True
    assert item["default_portion_grams"] == "250.0"
    assert item["per_100g"]["calories_kcal"] == "187.00"
    # Top-K 候選供使用者改選（FR-035），且候選也帶 per_100g 以便改選後重算。
    assert len(item["candidates"]) == 2
    assert item["candidates"][1]["name"] == "白飯"
    assert item["candidates"][1]["per_100g"]["calories_kcal"] == "130.00"


async def test_recognition_job_records_duration_for_oq1_calibration(
    client, upstream, seeded_foods, db_session
):
    upstream(lambda request: httpx.Response(200, json=NORMAL_RESPONSE))
    async with client as ac:
        response = await ac.post("/api/v1/recognitions", files=upload())

    job = db_session.get(RecognitionJob, uuid.UUID(response.json()["id"]))
    assert job.duration_ms is not None
    assert job.status == STATUS_COMPLETED
    assert job.item_count == 1


# --------------------------------------------------------------------------
# ★ 未偵測到食物：成功而非錯誤（FR-027）
# --------------------------------------------------------------------------


async def test_no_food_detected_returns_200_completed_not_an_error(
    client, upstream, seeded_foods, db_session
):
    upstream(lambda request: httpx.Response(200, json=EMPTY_RESPONSE))

    async with client as ac:
        response = await ac.post("/api/v1/recognitions", files=upload())

    assert response.status_code == 200, "未偵測到食物必須走成功路徑，不得回錯誤碼"
    body = response.json()
    assert body["status"] == STATUS_COMPLETED
    assert body["items"] == []
    # 服務訊息原樣保留，供前端引導畫面顯示。
    assert body["message"] == "沒有偵測到食物，請換一張再試試"
    assert "error" not in body

    job = db_session.get(RecognitionJob, uuid.UUID(body["id"]))
    assert job.status == STATUS_COMPLETED
    assert job.item_count == 0
    assert job.error_code is None
    assert job.no_food_detected is True


# --------------------------------------------------------------------------
# 錯誤分支
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("make_response", "expected_status", "expected_code"),
    [
        (lambda request: httpx.Response(500, json={"detail": "x"}), 503, "RECOGNITION_UNAVAILABLE"),
        (lambda request: httpx.Response(200, text="<html>"), 502, "RECOGNITION_BAD_RESPONSE"),
    ],
)
async def test_recognition_failures_map_to_documented_codes(
    client, upstream, seeded_foods, make_response, expected_status, expected_code
):
    upstream(make_response)
    async with client as ac:
        response = await ac.post("/api/v1/recognitions", files=upload())

    assert response.status_code == expected_status
    error = response.json()["error"]
    assert error["code"] == expected_code
    # 這些情境使用者可重試，前端據此顯示「重試」按鈕。
    assert error["retryable"] is True
    assert error["message"]


async def test_timeout_maps_to_504(client, upstream, seeded_foods):
    def handler(request):
        raise httpx.TimeoutException("timed out", request=request)

    upstream(handler)
    async with client as ac:
        response = await ac.post("/api/v1/recognitions", files=upload())

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "RECOGNITION_TIMEOUT"


async def test_failed_job_is_persisted_with_error_code(client, upstream, seeded_foods, db_session):
    upstream(lambda request: httpx.Response(500, json={"detail": "x"}))
    async with client as ac:
        await ac.post("/api/v1/recognitions", files=upload())

    job = db_session.query(RecognitionJob).one()
    assert job.status == STATUS_FAILED
    assert job.error_code == "UNAVAILABLE"


# --------------------------------------------------------------------------
# 上傳驗證
# --------------------------------------------------------------------------


async def test_unsupported_media_type_rejected_before_recognition(client, upstream, seeded_foods):
    called = {"count": 0}

    def handler(request):
        called["count"] += 1
        return httpx.Response(200, json=NORMAL_RESPONSE)

    upstream(handler)
    async with client as ac:
        response = await ac.post(
            "/api/v1/recognitions", files=upload(content_type="application/pdf")
        )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert called["count"] == 0, "格式不符時不應呼叫辨識服務"


async def test_oversized_photo_rejected(client, upstream, seeded_foods, monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.recognitions.get_settings",
        lambda: type(
            "S",
            (),
            {
                "photo_allowed_content_types": ("image/jpeg",),
                "photo_max_bytes": 10,
            },
        )(),
    )
    async with client as ac:
        response = await ac.post("/api/v1/recognitions", files=upload(b"x" * 100))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


# --------------------------------------------------------------------------
# 重試（FR-028）與資料隔離（FR-044）
# --------------------------------------------------------------------------


async def test_retry_reuses_stored_photo_without_reupload(
    client, upstream, seeded_foods, db_session
):
    responses = [
        httpx.Response(500, json={"detail": "fail"}),
        httpx.Response(200, json=NORMAL_RESPONSE),
    ]
    upstream(lambda request: responses.pop(0))

    async with client as ac:
        first = await ac.post("/api/v1/recognitions", files=upload())
        assert first.status_code == 503

        job = db_session.query(RecognitionJob).one()
        # 重試不帶任何檔案——照片由後端從既有路徑重讀。
        retry = await ac.post(f"/api/v1/recognitions/{job.id}/retry")

    assert retry.status_code == 200
    body = retry.json()
    assert body["status"] == STATUS_COMPLETED
    assert body["retry_count"] == 1
    assert len(body["items"]) == 1


async def test_cannot_access_another_users_recognition(
    client, upstream, seeded_foods, db_session, other_user
):
    foreign_job = RecognitionJob(
        user_id=other_user.id, status=STATUS_COMPLETED, photo_path="other/x.jpg"
    )
    db_session.add(foreign_job)
    db_session.flush()

    async with client as ac:
        response = await ac.get(f"/api/v1/recognitions/{foreign_job.id}")

    # 回 404 而非 403，避免洩漏資源是否存在。
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
