"""店家菜單上的餐點及其營養數值。

⚠️ 與第一輪的 MealItem 只差兩個字母，語意完全不同
==================================================
    MealItem  (meal_items)  使用者拍照記錄下來的一項食物，數值為寫入
                            當下的快照，屬於使用者的飲食紀錄
    MenuItem  (menu_items)  店家菜單上的一道菜，數值由店家登錄

兩者**無任何關聯、無外鍵、不得互相參照**（憲章原則 V）。撰寫 import 時
務必確認取用的是哪一個。

★ 四個營養欄位為何可為空值
==========================
    NULL = 店家未提供此項數值
    0    = 該項確實為零（零卡飲料、無脂餐點）

**兩者語意不同，不得互相代替。** 若設為 NOT NULL，管理員遇到店家沒提供
蛋白質資料時會被迫填一個 0——那不是缺資料，那是系統主動寫入了錯誤資料，
且「未提供」與「確實為 0」的區別在寫入當下就永久喪失，無法事後還原。

此項由第二輪於其 plan 階段提出（其 OQ-2b），2026-08-04 定案採 nullable，
已同步回共用契約。四個欄位彼此獨立，不要求同時填寫或同時留空——與 Store
的座標成對規則不同，不可比照。
"""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.db.models.store import Store


class MenuItem(Base, TimestampMixin):
    __tablename__ = "menu_items"
    __table_args__ = (
        # >= 0 而非 > 0：0 是合法值（FR-032）。
        # PostgreSQL 的 CHECK 在欄位為 NULL 時求值為 UNKNOWN，而 CHECK 只在
        # 結果為 FALSE 時才拒絕，故空值可正常寫入，不需額外寫 IS NULL OR。
        CheckConstraint("calories >= 0", name="ck_menu_items_calories"),
        CheckConstraint("protein_g >= 0", name="ck_menu_items_protein"),
        CheckConstraint("carbs_g >= 0", name="ck_menu_items_carbs"),
        CheckConstraint("fat_g >= 0", name="ck_menu_items_fat"),
        # 主要查詢型態是「取某店家底下的所有餐點」，屬明確的外鍵查詢。
        Index("ix_menu_items_store", "store_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    #: 強歸屬：餐點不能脫離店家存在。ON DELETE CASCADE 讓刪除店家時餐點
    #: 一併消失，不留孤兒資料（FR-037、FR-040）。
    #:
    #: 與第一輪 meal_items.food_reference_id 的 SET NULL 語意不同——那是
    #: 弱關聯（僅供來源追溯，刪除對照表不該刪掉使用者的歷史紀錄），此處
    #: 是強歸屬，兩者不可比照。
    store_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
    )

    #: 不設 UNIQUE——同店家內允許同名餐點（例如大小份未在名稱中區分）。
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- 營養數值：皆為選填，NULL ≠ 0（見模組說明）---
    calories: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    protein_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    carbs_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    fat_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    store: Mapped["Store"] = relationship(back_populates="menu_items")


__all__ = ["MenuItem"]
