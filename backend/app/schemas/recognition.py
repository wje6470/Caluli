"""辨識相關 schemas。欄位與 contracts/openapi.yaml 一致。"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Per100g(BaseModel):
    """每 100 公克的營養值。

    ⚠️ 此欄位為**必要**。前端靠它做份量即時換算而不再呼叫後端
    （research.md R-09）；移除將使份量即時調整無法運作。

    辨識服務本身不提供此欄位（只給估計份量下的絕對值），由
    `recognition_client.build_items()` 反推得出，對此 schema 透明
    （research.md R-16）。
    """

    model_config = ConfigDict(frozen=True)

    calories_kcal: Decimal
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class FoodCandidate(BaseModel):
    """Top-K 候選之一，依信心度排序（FR-035）。

    本輪實際串接的辨識服務不提供候選清單，`RecognitionItem.candidates`
    恆為空陣列；型別保留供未來服務改回提供候選時沿用（research.md R-16）。
    """

    food_reference_id: uuid.UUID | None = None
    name: str
    confidence: float
    default_portion_grams: Decimal | None = None
    per_100g: Per100g | None = None


class RecognitionItem(BaseModel):
    food_reference_id: uuid.UUID | None = None
    name: str
    confidence: float | None = None
    default_portion_grams: Decimal | None = None
    per_100g: Per100g | None = None
    #: false = 對照表查無資料，前端須標示無法自動換算（FR-037）。
    nutrition_available: bool
    candidates: list[FoodCandidate] = Field(default_factory=list)
    bounding_box: BoundingBox | None = None


class Recognition(BaseModel):
    """辨識資源。

    刻意採資源導向（帶 id 與 status）而非單純回傳 items 陣列：
    本輪同步實作下 status 只會是 completed／failed，但改為非同步時
    可直接回 202 + processing 而不破壞契約（research.md R-07）。
    """

    id: uuid.UUID
    status: str
    #: 空陣列 = 未偵測到食物，**仍為 completed**，不是錯誤（FR-027）。
    items: list[RecognitionItem] = Field(default_factory=list)
    #: 辨識服務回傳的說明訊息，原樣保留供前端顯示。
    message: str | None = None
    retry_count: int = 0
    requested_at: datetime
    completed_at: datetime | None = None


class FoodReferenceOut(BaseModel):
    id: uuid.UUID
    name: str
    default_portion_grams: Decimal
    per_100g: Per100g


class FoodSearchResponse(BaseModel):
    foods: list[FoodReferenceOut]
