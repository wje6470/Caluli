"""飲食紀錄（一次記帳）。"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.db.models.meal_item import MealItem

MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")


class MealRecord(Base, TimestampMixin):
    __tablename__ = "meal_records"
    __table_args__ = (
        CheckConstraint(
            "meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')",
            name="ck_meal_records_meal_type",
        ),
        # 儀表板與趨勢查詢的主要路徑。
        Index("ix_meal_records_user_date", "user_id", "record_date"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    #: 歸屬日期，依 APP_TIMEZONE 由 captured_at 換算後**物化**（FR-040）。
    #: 物化而非查詢時換算，讓「這筆屬於哪一天」成為可稽核的既定事實，
    #: 也讓日期彙總可直接走索引。
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    meal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    #: 相對於 PHOTO_STORAGE_ROOT。純手動修正情境下可為 NULL。
    photo_path: Mapped[str | None] = mapped_column(String(512))

    #: 來源辨識工作，供追溯。**刻意不設外鍵**——刪除 job 不應牽動紀錄。
    recognition_job_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))

    note: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["MealItem"]] = relationship(
        back_populates="meal_record",
        cascade="all, delete-orphan",
        order_by="MealItem.display_order",
        lazy="selectin",
    )
