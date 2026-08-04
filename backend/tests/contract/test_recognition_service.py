"""辨識服務契約測試（tasks.md T046，2026-08-04 依 Phase 3.1 更新為真實契約）。

驗證兩件事：
  1. stub 服務的七種模式確實回傳 contracts/recognition-service.md 文件化的形狀
  2. adapter 對每種形狀的分類與轉換正確（成功 / 空結果 / 三類錯誤 / 反推 per_100g）

契約狀態：已確認（OQ-3 關閉），見 contracts/recognition-service.md。
"""

import httpx
import pytest
from stub import app as stub_app

from app.db.models import ERROR_BAD_RESPONSE, ERROR_TIMEOUT, ERROR_UNAVAILABLE
from app.services.recognition_client import (
    DEFAULT_EMPTY_MESSAGE,
    RecognitionServiceError,
    build_items,
    call_recognition_service,
)

PHOTO = b"\xff\xd8\xff\xe0fake-jpeg-bytes"


# --------------------------------------------------------------------------
# 1. stub 本身符合契約文件
# --------------------------------------------------------------------------


async def stub_detect(mode: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=stub_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://stub") as client:
        return await client.post(
            "/api/detect", files={"file": ("p.jpg", PHOTO, "image/jpeg")}, params={"mode": mode}
        )


async def test_stub_normal_returns_items_with_absolute_nutrients():
    response = await stub_detect("normal")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) >= 1

    first = payload["items"][0]
    for key in ("name", "estimated_weight_g", "calories", "protein_g", "carbs_g", "fat_g",
                "confidence", "class_name", "bbox"):
        assert key in first
    assert set(first["bbox"]) == {"x1", "y1", "x2", "y2"}

    # 真實服務不提供候選清單。
    assert "candidates" not in first
    assert "message" not in payload


async def test_stub_empty_matches_confirmed_format():
    """真實服務的空結果不含 message，形狀必須完全一致。"""
    response = await stub_detect("empty")
    assert response.status_code == 200
    assert response.json() == {"items": []}


async def test_stub_error_returns_5xx():
    response = await stub_detect("error")
    assert response.status_code >= 500


async def test_stub_unauthorized_returns_401():
    response = await stub_detect("unauthorized")
    assert response.status_code == 401


async def test_stub_garbage_returns_non_json():
    response = await stub_detect("garbage")
    with pytest.raises(ValueError):
        response.json()


async def test_stub_zero_weight_returns_unusable_weight():
    response = await stub_detect("zero_weight")
    payload = response.json()
    assert payload["items"][0]["estimated_weight_g"] == 0


# --------------------------------------------------------------------------
# 2. adapter 對每種回應的分類與轉換
# --------------------------------------------------------------------------


def patched_client(handler):
    """把 adapter 內部建立的 AsyncClient 導向 MockTransport。"""
    transport = httpx.MockTransport(handler)

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    return PatchedAsyncClient


@pytest.fixture
def mock_upstream(monkeypatch):
    def install(handler):
        monkeypatch.setattr(
            "app.services.recognition_client.httpx.AsyncClient", patched_client(handler)
        )

    return install


NORMAL_ITEM = {
    "name": "滷肉飯",
    "estimated_weight_g": 250,
    "calories": 535.0,
    "protein_g": 20.0,
    "carbs_g": 60.0,
    "fat_g": 22.5,
    "confidence": 0.93,
    "class_name": "braised_pork_over_rice",
    "bbox": {"x1": 120, "y1": 80, "x2": 340, "y2": 260},
}


async def test_adapter_parses_successful_response(mock_upstream):
    mock_upstream(lambda request: httpx.Response(200, json={"items": [NORMAL_ITEM]}))
    result = await call_recognition_service(PHOTO)
    assert len(result.items) == 1
    assert result.items[0]["name"] == "滷肉飯"
    assert result.duration_ms >= 0


async def test_adapter_treats_empty_items_as_success_not_error(mock_upstream):
    """★ 未偵測到食物是**成功**的辨識結果，不得走錯誤路徑（FR-027）。"""
    mock_upstream(lambda request: httpx.Response(200, json={"items": []}))
    result = await call_recognition_service(PHOTO)  # 不應拋出例外
    assert result.items == []
    assert result.message is None  # 上游不提供，由呼叫端（recognitions.py）合成


async def test_adapter_maps_timeout(mock_upstream):
    def handler(request):
        raise httpx.TimeoutException("timed out", request=request)

    mock_upstream(handler)
    with pytest.raises(RecognitionServiceError) as exc:
        await call_recognition_service(PHOTO)
    assert exc.value.error_code == ERROR_TIMEOUT
    assert exc.value.to_app_error().code == "RECOGNITION_TIMEOUT"
    assert exc.value.to_app_error().spec.status_code == 504
    assert exc.value.to_app_error().spec.retryable is True


async def test_adapter_maps_5xx_to_unavailable(mock_upstream):
    mock_upstream(lambda request: httpx.Response(500, json={"detail": "model failure"}))
    with pytest.raises(RecognitionServiceError) as exc:
        await call_recognition_service(PHOTO)
    assert exc.value.error_code == ERROR_UNAVAILABLE
    assert exc.value.to_app_error().spec.status_code == 503


async def test_adapter_maps_401_to_unavailable_without_leaking_details(mock_upstream):
    """缺少／錯誤的 X-API-Key 對外一律呈現為服務不可用（research.md R-16）。"""
    mock_upstream(
        lambda request: httpx.Response(401, json={"detail": "invalid or missing X-API-Key"})
    )
    with pytest.raises(RecognitionServiceError) as exc:
        await call_recognition_service(PHOTO)
    assert exc.value.error_code == ERROR_UNAVAILABLE
    app_error = exc.value.to_app_error()
    assert app_error.code == "RECOGNITION_UNAVAILABLE"
    assert "key" not in app_error.message.lower()
    assert "401" not in app_error.message


async def test_adapter_maps_connection_failure_to_unavailable(mock_upstream):
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    mock_upstream(handler)
    with pytest.raises(RecognitionServiceError) as exc:
        await call_recognition_service(PHOTO)
    assert exc.value.error_code == ERROR_UNAVAILABLE


async def test_adapter_maps_non_json_to_bad_response(mock_upstream):
    mock_upstream(lambda request: httpx.Response(200, text="<html>oops</html>"))
    with pytest.raises(RecognitionServiceError) as exc:
        await call_recognition_service(PHOTO)
    assert exc.value.error_code == ERROR_BAD_RESPONSE
    assert exc.value.to_app_error().spec.status_code == 502


async def test_adapter_maps_missing_items_key_to_bad_response(mock_upstream):
    mock_upstream(lambda request: httpx.Response(200, json={"message": "no items key"}))
    with pytest.raises(RecognitionServiceError) as exc:
        await call_recognition_service(PHOTO)
    assert exc.value.error_code == ERROR_BAD_RESPONSE


async def test_adapter_does_not_auto_retry(mock_upstream):
    """後端不自動重試——重試決定權交給使用者（research.md R-08）。"""
    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        return httpx.Response(500, json={"detail": "fail"})

    mock_upstream(handler)
    with pytest.raises(RecognitionServiceError):
        await call_recognition_service(PHOTO)
    assert calls["count"] == 1


# --------------------------------------------------------------------------
# 3. build_items()：反推 per_100g、防禦性檢查、恆為 null/空陣列的欄位
# --------------------------------------------------------------------------


def test_build_items_reverses_per_100g_from_absolute_values():
    items = build_items([NORMAL_ITEM])
    assert len(items) == 1
    item = items[0]

    assert item.name == "滷肉飯"
    assert item.food_reference_id is None
    assert item.candidates == []
    assert item.nutrition_available is True
    assert item.default_portion_grams == 250
    # 535.0 / 250 * 100 = 214.0
    assert float(item.per_100g.calories_kcal) == pytest.approx(214.0)
    assert float(item.per_100g.protein_g) == pytest.approx(8.0)
    assert float(item.per_100g.carbs_g) == pytest.approx(24.0)
    assert float(item.per_100g.fat_g) == pytest.approx(9.0)

    assert item.bounding_box is not None
    assert item.bounding_box.x == 120
    assert item.bounding_box.y == 80
    assert item.bounding_box.width == 220  # 340 - 120
    assert item.bounding_box.height == 180  # 260 - 80


def test_build_items_degrades_gracefully_when_weight_is_zero():
    """estimated_weight_g = 0 時無法反推 per_100g，仍列出名稱不使整次失敗。"""
    zero_item = {**NORMAL_ITEM, "estimated_weight_g": 0}
    items = build_items([zero_item])
    assert len(items) == 1
    item = items[0]
    assert item.name == "滷肉飯"
    assert item.nutrition_available is False
    assert item.per_100g is None
    assert item.default_portion_grams is None


def test_build_items_handles_missing_bbox():
    item_without_bbox = {**NORMAL_ITEM, "bbox": None}
    items = build_items([item_without_bbox])
    assert items[0].bounding_box is None


def test_default_empty_message_constant_is_used_for_synthesis():
    assert DEFAULT_EMPTY_MESSAGE == "沒有偵測到食物，請換一張再試試"
