"""辨識服務 adapter。

★ 這是與辨識服務契約的**唯一接觸點**（OQ-3）。實際契約若與
  contracts/recognition-service.md 的假定不同，改動範圍限於本模組的
  解析邏輯；recognition_jobs 資料表、對外 API 契約與前端皆不受影響。

★ 本輪為同步呼叫（OQ-1 待確認）。改為非同步時，本模組由「呼叫並等待」
  拆成「提交」與「查詢」兩個方法即可，其餘不動（research.md R-07）。

後端**不做自動重試**：自動重試會讓已經在等待的使用者等更久
（30s → 60s），且無法在等待期間給出有意義的回饋。重試決定權交給使用者
（research.md R-08）。
"""

import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
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
from app.schemas.recognition import BoundingBox, FoodCandidate, Per100g, RecognitionItem

logger = logging.getLogger(__name__)

#: error_code → 對外錯誤 code。
ERROR_CODE_MAP = {
    ERROR_TIMEOUT: "RECOGNITION_TIMEOUT",
    ERROR_UNAVAILABLE: "RECOGNITION_UNAVAILABLE",
    ERROR_BAD_RESPONSE: "RECOGNITION_BAD_RESPONSE",
}


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
    """辨識服務的原始回應（尚未查表換算）。"""

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
    url = f"{settings.recognition_service_url.rstrip('/')}/predict"
    params = {"mode": mode} if mode else None

    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=settings.recognition_timeout_seconds) as client:
            response = await client.post(
                url,
                files={"photo": ("photo.jpg", photo_bytes, "image/jpeg")},
                params=params,
            )
    except httpx.TimeoutException as exc:
        raise RecognitionServiceError(ERROR_TIMEOUT, str(exc)) from exc
    except httpx.HTTPError as exc:
        # 連線被拒、DNS 失敗等一律歸為服務不可用。
        raise RecognitionServiceError(ERROR_UNAVAILABLE, str(exc)) from exc

    duration_ms = int((time.monotonic() - started) * 1000)

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
        message=payload.get("message"),
        raw=payload,
        duration_ms=duration_ms,
    )


def _per_100g(ref: FoodNutritionReference) -> Per100g:
    return Per100g(
        calories_kcal=ref.calories_kcal_per_100g,
        protein_g=ref.protein_g_per_100g,
        carbs_g=ref.carbs_g_per_100g,
        fat_g=ref.fat_g_per_100g,
    )


def _load_references(db: Session, labels: set[str]) -> dict[str, FoodNutritionReference]:
    if not labels:
        return {}
    rows = db.scalars(
        select(FoodNutritionReference).where(
            FoodNutritionReference.model_label.in_(labels),
            FoodNutritionReference.is_active.is_(True),
        )
    ).all()
    return {row.model_label: row for row in rows}


def _collect_labels(raw_items: list[dict[str, Any]]) -> set[str]:
    labels: set[str] = set()
    for item in raw_items:
        if label := item.get("label"):
            labels.add(str(label))
        for candidate in item.get("candidates") or []:
            if label := candidate.get("label"):
                labels.add(str(label))
    return labels


def build_items(db: Session, raw_items: list[dict[str, Any]]) -> list[RecognitionItem]:
    """把模型輸出的分類標籤轉為帶營養值的辨識品項。

    辨識服務回傳的是**分類標籤**，不是營養資訊，也**不提供份量**——
    HF 分類模型無法估算克數。份量一律取自對照表的 default_portion_grams
    （系統設定值，非模型輸出，FR-022）。
    """
    references = _load_references(db, _collect_labels(raw_items))
    items: list[RecognitionItem] = []

    for raw in raw_items:
        label = str(raw.get("label") or "")
        ref = references.get(label)

        candidates: list[FoodCandidate] = []
        for raw_candidate in raw.get("candidates") or []:
            candidate_label = str(raw_candidate.get("label") or "")
            candidate_ref = references.get(candidate_label)
            candidates.append(
                FoodCandidate(
                    food_reference_id=candidate_ref.id if candidate_ref else None,
                    name=candidate_ref.name if candidate_ref else candidate_label,
                    confidence=float(raw_candidate.get("confidence") or 0.0),
                    default_portion_grams=(
                        candidate_ref.default_portion_grams if candidate_ref else None
                    ),
                    per_100g=_per_100g(candidate_ref) if candidate_ref else None,
                )
            )

        bbox_raw = raw.get("bbox")
        bounding_box = None
        if isinstance(bbox_raw, dict):
            try:
                bounding_box = BoundingBox(**bbox_raw)
            except (TypeError, ValueError):
                # bbox 格式異常不應讓整次辨識失敗——它只影響標註位置。
                logger.warning("辨識回應的 bbox 格式無法解析：%s", bbox_raw)

        items.append(
            RecognitionItem(
                food_reference_id=ref.id if ref else None,
                name=ref.name if ref else label,
                confidence=(
                    float(raw["confidence"]) if raw.get("confidence") is not None else None
                ),
                default_portion_grams=ref.default_portion_grams if ref else None,
                per_100g=_per_100g(ref) if ref else None,
                # 查表失敗：仍列出名稱，但標示無法自動換算（FR-038 / FR-037）。
                nutrition_available=ref is not None,
                candidates=candidates,
                bounding_box=bounding_box,
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
