"""儀表板與趨勢聚合。"""

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import date_range
from app.db.models import HealthProfile, MealItem, MealRecord
from app.schemas.analytics import DashboardResponse, MetricKey, TrendPoint, TrendResponse
from app.schemas.meal_record import Nutrients
from app.services import meal_records
from app.services.nutrition import Nutrients as DomainNutrients

ZERO = Decimal("0")

#: metric → meal_items 欄位。
METRIC_COLUMNS = {
    "calories": MealItem.calories_kcal,
    "protein": MealItem.protein_g,
    "carbs": MealItem.carbs_g,
    "fat": MealItem.fat_g,
}

#: metric → health_profiles 的目標欄位。
METRIC_TARGETS = {
    "calories": "tdee_kcal",
    "protein": "target_protein_g",
    "carbs": "target_carbs_g",
    "fat": "target_fat_g",
}


def _to_schema(nutrients: DomainNutrients) -> Nutrients:
    return Nutrients(
        calories_kcal=nutrients.calories_kcal,
        protein_g=nutrients.protein_g,
        carbs_g=nutrients.carbs_g,
        fat_g=nutrients.fat_g,
    )


def _targets_of(profile: HealthProfile | None) -> Nutrients:
    if profile is None:
        return Nutrients(calories_kcal=ZERO, protein_g=ZERO, carbs_g=ZERO, fat_g=ZERO)
    return Nutrients(
        calories_kcal=profile.tdee_kcal,
        protein_g=profile.target_protein_g,
        carbs_g=profile.target_carbs_g,
        fat_g=profile.target_fat_g,
    )


def build_dashboard(
    db: Session, user_id: uuid.UUID, profile: HealthProfile | None, on_date: date
) -> DashboardResponse:
    records = meal_records.list_records(db, user_id, on_date)

    consumed = DomainNutrients.zero()
    for record in records:
        consumed = consumed + meal_records.totals_of(record)

    targets = _targets_of(profile)
    consumed_schema = _to_schema(consumed)

    # 剩餘可用熱量 = 建議 − 已攝取。超標時為負值，讓前端能明確標示
    # 而非顯示誤導性的 0（FR-045、FR-048）。
    remaining = Nutrients(
        calories_kcal=targets.calories_kcal - consumed_schema.calories_kcal,
        protein_g=targets.protein_g - consumed_schema.protein_g,
        carbs_g=targets.carbs_g - consumed_schema.carbs_g,
        fat_g=targets.fat_g - consumed_schema.fat_g,
    )

    return DashboardResponse(
        date=on_date,
        targets=targets,
        consumed=consumed_schema,
        remaining=remaining,
        over_target=consumed_schema.calories_kcal > targets.calories_kcal > ZERO,
        records=[meal_records.to_out(record) for record in records],
    )


def build_trends(
    db: Session,
    user_id: uuid.UUID,
    profile: HealthProfile | None,
    range_days: int,
    metric: MetricKey,
    end: date,
) -> TrendResponse:
    column = METRIC_COLUMNS[metric]
    days = date_range(end, range_days)

    stmt = (
        select(MealRecord.record_date, func.sum(column))
        .join(MealItem, MealItem.meal_record_id == MealRecord.id)
        .where(
            MealRecord.user_id == user_id,
            MealRecord.record_date >= days[0],
            MealRecord.record_date <= days[-1],
        )
        .group_by(MealRecord.record_date)
    )
    totals: dict[date, Decimal] = {row[0]: row[1] or ZERO for row in db.execute(stmt)}

    # ★ FR-054：由後端補齊完整日期序列，沒有紀錄的日期填 0——
    # 不依賴資料庫產生空列，也不讓前端自行推斷。
    points = [TrendPoint(date=day, value=totals.get(day, ZERO)) for day in days]

    total = sum((point.value for point in points), ZERO)
    average = (total / len(points)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    target: Decimal | None = None
    if profile is not None:
        target = getattr(profile, METRIC_TARGETS[metric])

    # 達標定義：該日攝取達目標的 90%~110% 之間。過與不及都不算達標。
    achievement = ZERO
    if target and target > ZERO:
        hit = sum(
            1
            for point in points
            if target * Decimal("0.9") <= point.value <= target * Decimal("1.1")
        )
        achievement = (Decimal(hit) / len(points)).quantize(
            Decimal("0.001"), rounding=ROUND_HALF_UP
        )

    return TrendResponse(
        range_days=range_days,
        metric=metric,
        points=points,
        target=target,
        average=average,
        target_achievement_rate=achievement,
    )
