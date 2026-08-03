"""儀表板與趨勢端點。"""

from datetime import date

from fastapi import APIRouter, Query

from app.core.clock import today
from app.core.deps import CurrentUser, DbSession
from app.schemas.analytics import DashboardResponse, MetricKey, TrendResponse
from app.services import analytics

router = APIRouter(tags=["analytics"])


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    db: DbSession,
    user: CurrentUser,
    on_date: date | None = Query(default=None, alias="date"),
) -> DashboardResponse:
    return analytics.build_dashboard(db, user.id, user.health_profile, on_date or today())


@router.get("/trends", response_model=TrendResponse)
def get_trends(
    db: DbSession,
    user: CurrentUser,
    range_days: int = Query(alias="range_days"),
    metric: MetricKey = Query(default="calories"),
) -> TrendResponse:
    # 只開放三種區間，避免任意大範圍查詢。
    allowed = {7, 14, 30}
    days = range_days if range_days in allowed else 7
    return analytics.build_trends(db, user.id, user.health_profile, days, metric, today())
