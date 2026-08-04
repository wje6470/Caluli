"""辨識服務 adapter。

★ 這是與辨識服務契約的**唯一接觸點**（research.md R-16）。契約差異全部
  收斂於本模組：對外（前端／`contracts/openapi.yaml`）維持不變的
  `Recognition`／`RecognitionItem` 形狀，對內改為呼叫第三方代管的
  「台灣小吃辨識 API」（`contracts/recognition-service.md`）。

★ 本輪為同步呼叫（OQ-1 待確認）。改為非同步時，本模組由「呼叫並等待」
  拆成「提交」與「查詢」兩個方法即可，其餘不動（research.md R-07）。

辨識服務回傳的是**每個品項在其估計份量下的絕對營養值**（`calories` /
`protein_g` / `carbs_g` / `fat_g` / `estimated_weight_g`），不是分類標籤，
也不提供每 100g 值或候選清單——與本模組初版假定的契約相反。本模組負責
以 `value / estimated_weight_g × 100` 反推 `per_100g`，讓對外契約維持
「前端不呼叫後端即可即時換算」的既有形狀（research.md R-09、R-16）。

後端**不做自動重試**：自動重試會讓已經在等待的使用者等更久
（30s → 60s），且無法在等待期間給出有意義的回饋。重試決定權交給使用者
（research.md R-08）。
"""

import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import (
    ERROR_BAD_RESPONSE,
    ERROR_TIMEOUT,
    ERROR_UNAVAILABLE,
    FoodNutritionReference,
)
from app.schemas.recognition import BoundingBox, Per100g, RecognitionItem

logger = logging.getLogger(__name__)

#: error_code → 對外錯誤 code。
ERROR_CODE_MAP = {
    ERROR_TIMEOUT: "RECOGNITION_TIMEOUT",
    ERROR_UNAVAILABLE: "RECOGNITION_UNAVAILABLE",
    ERROR_BAD_RESPONSE: "RECOGNITION_BAD_RESPONSE",
}

#: 上游不提供空結果的說明文字，由本層合成固定文案（見 contracts/recognition-service.md）。
DEFAULT_EMPTY_MESSAGE = "沒有偵測到食物，請換一張再試試"


class RecognitionServiceError(Exception):
    """辨識服務呼叫失敗。error_code 對應 recognition_jobs.error_code。"""

    def __init__(self, error_code: str, detail: str = ""):
        self.error_code = error_code
        self.detail = detail
        super().__init__(f"{error_code}: {detail}")

    def to_app_error(self) -> AppError:
        return AppError(ERROR_CODE_MAP[self.error_code], detail=self.detail)


@dataclass
class RawRecognition:
    """辨識服務的原始回應（尚未反推 per_100g）。"""

    items: list[dict[str, Any]] = field(default_factory=list)
    message: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0


async def call_recognition_service(
    photo_bytes: bytes, *, mode: str | None = None
) -> RawRecognition:
    """同步等待辨識服務回應。

    mode 僅供 stub 服務切換模式使用，正式服務會忽略。
    """
    settings = get_settings()
    url = f"{settings.recognition_service_url.rstrip('/')}/api/detect"
    params = {"mode": mode} if mode else None
    headers = (
        {"X-API-Key": settings.recognition_api_key} if settings.recognition_api_key else None
    )

    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=settings.recognition_timeout_seconds) as client:
            response = await client.post(
                url,
                files={"file": ("photo.jpg", photo_bytes, "image/jpeg")},
                params=params,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise RecognitionServiceError(ERROR_TIMEOUT, str(exc)) from exc
    except httpx.HTTPError as exc:
        # 連線被拒、DNS 失敗等一律歸為服務不可用。
        raise RecognitionServiceError(ERROR_UNAVAILABLE, str(exc)) from exc

    duration_ms = int((time.monotonic() - started) * 1000)

    if response.status_code == 401:
        # 缺少或錯誤的 X-API-Key。對外一律呈現為服務不可用，不揭露認證細節（R-16）。
        raise RecognitionServiceError(ERROR_UNAVAILABLE, "upstream authentication failed")
    if response.status_code >= 500:
        raise RecognitionServiceError(ERROR_UNAVAILABLE, f"upstream status {response.status_code}")
    if response.status_code >= 400:
        raise RecognitionServiceError(ERROR_BAD_RESPONSE, f"upstream status {response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise RecognitionServiceError(ERROR_BAD_RESPONSE, "response is not JSON") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise RecognitionServiceError(ERROR_BAD_RESPONSE, "missing 'items' array")

    return RawRecognition(
        items=payload["items"],
        # 上游不提供 message 欄位；為 None 時由呼叫端合成 DEFAULT_EMPTY_MESSAGE。
        message=payload.get("message"),
        raw=payload,
        duration_ms=duration_ms,
    )


def _reverse_per_100g(value: Any, weight_grams: Decimal) -> Decimal:
    """由『該估計份量下的絕對值』反推每 100 公克單位值。"""
    return Decimal(str(value)) / weight_grams * 100


def _build_bounding_box(bbox_raw: Any) -> BoundingBox | None:
    """轉換座標格式：辨識服務給 {x1,y1,x2,y2}，對外契約是 {x,y,width,height}。"""
    if not isinstance(bbox_raw, dict):
        return None
    try:
        x1 = float(bbox_raw["x1"])
        y1 = float(bbox_raw["y1"])
        x2 = float(bbox_raw["x2"])
        y2 = float(bbox_raw["y2"])
    except (KeyError, TypeError, ValueError):
        # bbox 格式異常不應讓整次辨識失敗——它只影響標註位置。
        logger.warning("辨識回應的 bbox 格式無法解析：%s", bbox_raw)
        return None
    return BoundingBox(x=x1, y=y1, width=x2 - x1, height=y2 - y1)


def build_items(raw_items: list[dict[str, Any]]) -> list[RecognitionItem]:
    """把辨識服務回傳的絕對營養值轉為前端消費的 per_100g 形狀。

    辨識服務直接提供每個品項的熱量與三大營養素（該估計份量下的絕對值），
    不再是待查表的分類標籤，故本函式**不查詢** `food_nutrition_references`
    ——`food_reference_id` 一律為 None，該表現在僅供 `search_foods()`
    （FR-037 手動修正）使用（research.md R-16 決策 2）。
    """
    items: list[RecognitionItem] = []

    for raw in raw_items:
        name = str(raw.get("name") or "")
        weight_raw = raw.get("estimated_weight_g")

        default_portion_grams: Decimal | None = None
        per_100g: Per100g | None = None
        nutrition_available = False

        try:
            weight_grams = Decimal(str(weight_raw))
        except (TypeError, ValueError, InvalidOperation):
            weight_grams = None

        if weight_grams is not None and weight_grams > 0:
            try:
                per_100g = Per100g(
                    calories_kcal=_reverse_per_100g(raw.get("calories"), weight_grams),
                    protein_g=_reverse_per_100g(raw.get("protein_g"), weight_grams),
                    carbs_g=_reverse_per_100g(raw.get("carbs_g"), weight_grams),
                    fat_g=_reverse_per_100g(raw.get("fat_g"), weight_grams),
                )
                default_portion_grams = weight_grams
                nutrition_available = True
            except (TypeError, ValueError, InvalidOperation):
                # 絕對值缺漏或格式異常：仍列出名稱，標示無法自動換算（FR-037）。
                logger.warning("辨識品項的營養值無法反推 per_100g：%s", raw)

        items.append(
            RecognitionItem(
                food_reference_id=None,
                name=name,
                confidence=(
                    float(raw["confidence"]) if raw.get("confidence") is not None else None
                ),
                default_portion_grams=default_portion_grams,
                per_100g=per_100g,
                nutrition_available=nutrition_available,
                candidates=[],
                bounding_box=_build_bounding_box(raw.get("bbox")),
            )
        )

    return items


def search_foods(db: Session, query: str, limit: int = 20) -> list[FoodNutritionReference]:
    """供手動修正食物名稱使用（FR-037）。僅查通用食物對照表。"""
    from app.db.models import normalize_food_name

    normalized = normalize_food_name(query)
    stmt = (
        select(FoodNutritionReference)
        .where(
            FoodNutritionReference.is_active.is_(True),
            FoodNutritionReference.name_normalized.ilike(f"%{normalized}%"),
        )
        .order_by(FoodNutritionReference.name)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def to_per_100g_decimal(value: Any) -> Decimal:
    return Decimal(str(value))
