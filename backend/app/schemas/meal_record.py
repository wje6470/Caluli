"""飲食紀錄 schemas。"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.recognition import Per100g

MealType = Literal["breakfast", "lunch", "dinner", "snack"]


class Nutrients(BaseModel):
    model_config = ConfigDict(frozen=True)

    calories_kcal: Decimal
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal


class MealItemInput(BaseModel):
    """單一品項輸入。

    ⚠️ 客戶端**不送**換算後的營養值——後端一律以 per_100g × portion_grams
    重新計算（research.md R-09）。前端算出來的數值只用於畫面即時回饋。
    """

    food_reference_id: uuid.UUID | None = None
    food_name: str = Field(min_length=1, max_length=255)
    portion_grams: Decimal = Field(gt=0, le=5000)
    default_portion_grams: Decimal | None = None
    per_100g: Per100g
    recognition_confidence: float | None = Field(default=None, ge=0, le=1)
    is_user_modified: bool = False


class MealItemOut(BaseModel):
    id: uuid.UUID
    food_reference_id: uuid.UUID | None = None
    food_name: str
    portion_grams: Decimal
    default_portion_grams: Decimal | None = None
    per_100g: Per100g
    recognition_confidence: float | None = None
    is_user_modified: bool
    #: 後端驗算後的權威數值。
    nutrients: Nutrients


class MealRecordInput(BaseModel):
    recognition_id: uuid.UUID | None = None
    meal_type: MealType
    captured_at: datetime | None = None
    items: list[MealItemInput] = Field(min_length=1)


class MealRecordOut(BaseModel):
    id: uuid.UUID
    record_date: date
    meal_type: MealType
    captured_at: datetime
    has_photo: bool
    items: list[MealItemOut]
    totals: Nutrients


class MealRecordListResponse(BaseModel):
    records: list[MealRecordOut]
