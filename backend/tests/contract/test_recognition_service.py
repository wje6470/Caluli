"""辨識服務契約測試（tasks.md T046）。

驗證兩件事：
  1. stub 服務的六種模式確實回傳 contracts/recognition-service.md 文件化的形狀
  2. adapter 對每種形狀的分類正確（成功 / 空結果 / 三類錯誤）

⚠️ 契約狀態：目前只有「錯誤／空結果格式」經確認（OQ-3），其餘為假定。
   實際契約若不同，需同步更新本測試與 recognition_client.py。
"""

import httpx
import pytest
from stub import app as stub_app

from app.db.models import ERROR_BAD_RESPONSE, ERROR_TIMEOUT, ERROR_UNAVAILABLE
from app.services.recognition_client import (
    RecognitionServiceError,
    call_recognition_service,
)

PHOTO = b"\xff\xd8\xff\xe0fake-jpeg-bytes"


# --------------------------------------------------------------------------
# 1. stub 本身符合契約文件
# --------------------------------------------------------------------------


async def stub_predict(mode: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=stub_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://stub") as client:
        return await client.post(
            "/predict", files={"photo": ("p.jpg", PHOTO, "image/jpeg")}, params={"mode": mode}
        )


async def test_stub_normal_returns_items_with_candidates():
    response = await stub_predict("normal")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) >= 1

    first = payload["items"][0]
    assert "label" in first
    assert "confidence" in first
    assert isinstance(first["candidates"], list)
    # HF Top-K 依信心度排序。
    confidences = [c["confidence"] for c in first["candidates"]]
    assert confidences == sorted(confidences, reverse=True)

    # ⚠️ 模型**不提供**份量資訊——這是預設份量流程存在的原因（FR-022）。
    for key in ("grams", "portion", "weight", "portion_grams"):
        assert key not in first


async def test_stub_empty_matches_confirmed_error_format():
    """這是唯一經確認的格式，形狀必須完全一致。"""
    response = await stub_predict("empty")
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "message": "沒有偵測到食物，請換一張再試試",
    }


async def test_stub_error_returns_5xx():
    response = await stub_predict("error")
    assert response.status_code >= 500


async def test_stub_garbage_returns_non_json():
    response = await stub_predict("garbage")
    with pytest.raises(ValueError):
        response.json()


async def test_stub_unknown_label_returns_label_absent_from_reference_table():
    response = await stub_predict("unknown_label")
    payload = response.json()
    assert payload["items"][0]["label"] == "label_not_in_reference_table"


# --------------------------------------------------------------------------
# 2. adapter 對每種回應的分類
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


async def test_adapter_parses_successful_response(mock_upstream):
    mock_upstream(
        lambda request: httpx.Response(
            200,
            json={"items": [{"label": "braised_pork_rice", "confidence": 0.93}], "message": None},
        )
    )
    result = await call_recognition_service(PHOTO)
    assert len(result.items) == 1
    assert result.items[0]["label"] == "braised_pork_rice"
    assert result.duration_ms >= 0


async def test_adapter_treats_empty_items_as_success_not_error(mock_upstream):
    """★ 未偵測到食物是**成功**的辨識結果，不得走錯誤路徑（FR-027）。"""
    mock_upstream(
        lambda request: httpx.Response(
            200, json={"items": [], "message": "沒有偵測到食物，請換一張再試試"}
        )
    )
    result = await call_recognition_service(PHOTO)  # 不應拋出例外
    assert result.items == []
    assert result.message == "沒有偵測到食物，請換一張再試試"


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
