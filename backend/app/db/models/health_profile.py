"""個人健康檔案與由此推導的每日目標。與 User 為 1:1。"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.db.models.user import User

GENDERS = ("male", "female")
ACTIVITY_LEVELS = ("low", "moderate", "high")


class HealthProfile(Base, TimestampMixin):
    __tablename__ = "health_profiles"
    __table_args__ = (
        CheckConstraint("gender IN ('male', 'female')", name="ck_health_profiles_gender"),
        CheckConstraint(
            "activity_level IN ('low', 'moderate', 'high')",
            name="ck_health_profiles_activity_level",
        ),
        # FR-014 的合理生理範圍。與 Pydantic schema 雙層驗證：
        # API 層負責產生可讀的錯誤訊息，DB 層負責兜底。
        CheckConstraint("age_years BETWEEN 15 AND 90", name="ck_health_profiles_age"),
        CheckConstraint("height_cm BETWEEN 100 AND 250", name="ck_health_profiles_height"),
        CheckConstraint("weight_kg BETWEEN 25 AND 300", name="ck_health_profiles_weight"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # 1:1 由 UNIQUE 保證
    )

    gender: Mapped[str] = mapped_column(String(8), nullable=False)
    age_years: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    height_cm: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    activity_level: Mapped[str] = mapped_column(String(16), nullable=False)

    # 以下皆由 services/targets.py 計算後寫入，API 忽略客戶端傳入值。
    bmr_kcal: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    tdee_kcal: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    target_protein_g: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)
    target_carbs_g: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)
    target_fat_g: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="health_profile")
