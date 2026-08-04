"""餐點（menu_items）— 與第三輪管理員後台共用。

═══════════════════════════════════════════════════════════════════
⚠️ 合併時以**第三輪（feature/round3-admin）的版本為準**，本檔可直接覆蓋
═══════════════════════════════════════════════════════════════════
理由與欄位來源見同目錄的 store.py 檔頭。

⚠️ 不要與 meal_item.py 混淆
============================
`MenuItem`（本檔）＝ **店家登錄的餐點**營養值（第二／三輪，推薦餐廳）
`MealItem`（meal_item.py）＝ **使用者飲食紀錄**中的品項（第一輪，拍照記帳）

兩者只差兩個字母，卻分屬憲章原則 V 要求嚴格隔離的兩套資料體系，
誤用的代價很高——請確認 import 的是哪一個。
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
    """店家登錄的單一餐點及其營養數值。本輪唯讀。"""

    __tablename__ = "menu_items"
    __table_args__ = (
        CheckConstraint("calories IS NULL OR calories >= 0", name="ck_menu_items_calories"),
        CheckConstraint("protein_g IS NULL OR protein_g >= 0", name="ck_menu_items_protein"),
        CheckConstraint("carbs_g IS NULL OR carbs_g >= 0", name="ck_menu_items_carbs"),
        CheckConstraint("fat_g IS NULL OR fat_g >= 0", name="ck_menu_items_fat"),
        Index("ix_menu_items_store", "store_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    #: ON DELETE CASCADE：刪除店家連帶刪除其全部餐點，不留孤兒資料。
    #: 刪除為**實刪除**，資料表無 deleted_at／is_active——因此所有查詢
    #: 都**不得**加「排除已刪除」的過濾條件（FR-018a）。
    store_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
    )

    #: 餐點名稱。同店家內允許同名餐點，不強制唯一，查詢與呈現皆不得去重。
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # ------------------------------------------------------------------
    # 營養欄位：**nullable 是必要的，不是隨意的選擇**
    #
    #   NULL → 店家未提供 → 畫面顯示「無資料」
    #   0    → 店家登錄該營養素為零 → 畫面顯示 0
    #
    # 這兩者對使用者的意義不同（FR-025）。若改為 NOT NULL + 預設 0，
    # 「未填寫」與「確實為 0」的區別在寫入當下即永久喪失，事後無法還原。
    # 第三輪已確認 NULL 不會被寫成 0，並有測試專門斷言這點。
    #
    # ⚠️ 欄位名稱依共用契約為 `calories`（不是 calories_kcal）。API 回應
    #    層才轉為 calories_kcal 以沿用第一輪的命名慣例，見 schemas/store.py。
    # ------------------------------------------------------------------
    calories: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    protein_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    carbs_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    fat_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    store: Mapped["Store"] = relationship(back_populates="menu_items")
