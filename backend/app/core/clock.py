"""時區與日期歸屬（research.md R-12）。

紀錄的歸屬日期以固定時區 APP_TIMEZONE（預設 Asia/Taipei）換算後物化。
不依裝置回報的時區動態換算——否則使用者出國時，同一批歷史紀錄的歸屬日
會隨當下時區改變，趨勢圖會前後不一致。

未來若需支援跨時區使用者：於 health_profiles 加 timezone 欄位、寫入時
採用該值即可，現有結構不需破壞性變更。
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def app_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().app_timezone)


def now_utc() -> datetime:
    return datetime.now(UTC)


def to_record_date(moment: datetime) -> date:
    """把時間點換算為所屬的紀錄日期（FR-040）。"""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(app_tz()).date()


def today() -> date:
    return to_record_date(now_utc())


def date_range(end: date, days: int) -> list[date]:
    """回傳含 end 在內、往前共 days 天的完整日期序列。

    趨勢圖表的「沒有紀錄的日期以零呈現」（FR-054）靠這個序列補齊，
    而不是依賴資料庫產生空列。
    """
    start = end - timedelta(days=days - 1)
    return [start + timedelta(days=offset) for offset in range(days)]


def default_meal_type(moment: datetime | None = None) -> str:
    """依當下時間給餐別預設值（FR-038）。"""
    local = (moment or now_utc()).astimezone(app_tz())
    hour = local.hour
    if 4 <= hour < 11:
        return "breakfast"
    if 11 <= hour < 16:
        return "lunch"
    if 16 <= hour < 22:
        return "dinner"
    return "snack"
