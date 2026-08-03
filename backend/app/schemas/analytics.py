"""儀表板與趨勢 schemas。"""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.schemas.meal_record import MealRecordOut, Nutrients

MetricKey = Literal["calories", "protein", "carbs", "fat"]


class DashboardResponse(BaseModel):
    date: date
    targets: Nutrients
    consumed: Nutrients
    #: targets − consumed；已超標時為負值，前端須明確標示（FR-048）。
    remaining: Nutrients
    over_target: bool
    records: list[MealRecordOut]


class TrendPoint(BaseModel):
    date: date
    value: Decimal


class TrendResponse(BaseModel):
    range_days: int
    metric: MetricKey
    #: 完整日期序列——沒有紀錄的日期 value 為 0，不略過（FR-054）。
    points: list[TrendPoint]
    target: Decimal | None = None
    average: Decimal
    #: 區間內達標天數比例（0–1）。
    target_achievement_rate: Decimal
