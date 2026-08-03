"""飲食紀錄中的單一食物品項。

營養值採**寫入當下的快照**（research.md R-11）：若歷史紀錄透過外鍵即時
查詢營養值，日後修正對照表就會**追溯改變使用者的歷史攝取與趨勢圖**。
因此 food_reference_id 只是弱關聯（ON DELETE SET NULL），實際數值一律
存在本表。
"""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.db.models.meal_record import MealRecord


class MealItem(Base, TimestampMixin):
    __tablename__ = "meal_items"
    __table_args__ = (
        CheckConstraint(
            "portion_grams > 0 AND portion_grams <= 5000", name="ck_meal_items_portion"
        ),
        CheckConstraint("calories_kcal_per_100g >= 0", name="ck_meal_items_cal_per_100g"),
        CheckConstraint("protein_g_per_100g >= 0", name="ck_meal_items_pro_per_100g"),
        CheckConstraint("carbs_g_per_100g >= 0", name="ck_meal_items_carb_per_100g"),
        CheckConstraint("fat_g_per_100g >= 0", name="ck_meal_items_fat_per_100g"),
        CheckConstraint("calories_kcal >= 0", name="ck_meal_items_calories"),
        CheckConstraint("protein_g >= 0", name="ck_meal_items_protein"),
        CheckConstraint("carbs_g >= 0", name="ck_meal_items_carbs"),
        CheckConstraint("fat_g >= 0", name="ck_meal_items_fat"),
        CheckConstraint(
            "recognition_confidence IS NULL "
            "OR (recognition_confidence >= 0 AND recognition_confidence <= 1)",
            name="ck_meal_items_confidence",
        ),
        Index("ix_meal_items_record", "meal_record_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    meal_record_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("meal_records.id", ondelete="CASCADE"),
        nullable=False,
    )

    #: 僅供來源追溯。NULL = 使用者自行輸入的品項（FR-037）。
    #: SET NULL 而非 CASCADE——刪除對照項目不得刪掉使用者的歷史紀錄。
    food_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("food_nutrition_references.id", ondelete="SET NULL"),
    )

    display_order: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    food_name: Mapped[str] = mapped_column(String(255), nullable=False)

    #: 系統原本套用的預設份量，供分析「使用者調整幅度」。
    default_portion_grams: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    #: 使用者確認後的份量（FR-034）。
    portion_grams: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)

    # --- 每 100g 快照 ---
    calories_kcal_per_100g: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    protein_g_per_100g: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    carbs_g_per_100g: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    fat_g_per_100g: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    # --- 換算結果（後端驗算後寫入，客戶端數值不採信）---
    calories_kcal: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    protein_g: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    carbs_g: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    fat_g: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)

    recognition_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    is_user_modified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    meal_record: Mapped["MealRecord"] = relationship(back_populates="items")
