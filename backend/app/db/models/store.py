"""合作店家。

★ 欄位結構受共用契約約束
========================
本表由第二輪（推薦餐廳，讀取端）與第三輪（後台維護，寫入端）共用，欄位
結構完全依 reference/shared-schema-store-menu.md，**不得自行增減或更名**。
需要調整時必須先修訂契約並知會對方，不得單方變更。

★ 憲章原則 V：與通用食物營養對照表完全獨立
==========================================
本表與 food_nutrition_references 之間沒有任何外鍵，也不共用主鍵語意。
店家餐點的營養值是店家自行登錄的既定數值，通用對照表則是辨識模型的估算
基準，兩者正確性的責任歸屬不同，不得互相參照。
"""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.db.models.menu_item import MenuItem


class Store(Base, TimestampMixin):
    __tablename__ = "stores"
    __table_args__ = (
        # 座標必須成對：允許「都沒填」與「都填了」，但不允許只有一個。
        # 寫成布林等值比較是 PostgreSQL 中表達此語意最精簡的方式，也讓
        # FR-022 成為結構上不可能違反的約束，而非只靠應用層驗證。
        CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="ck_stores_coords_paired"),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_stores_latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_stores_longitude_range",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    #: 刻意**不設 UNIQUE**——連鎖分店同名是正常資料，以 address 區分（FR-027）。
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)

    #: 座標為**選填**（FR-021）：允許先建立名稱與地址、之後再補座標，
    #: 避免為了通過必填而填入一個不實的座標——錯座標比沒座標更難發現，
    #: 因為系統無從驗證地址與座標是否一致。
    #:
    #: 未設座標的店家不會出現在第二輪依距離排序的結果中（無距離可計算），
    #: 但在不排序的完整清單中仍正常出現。此規則已寫入共用契約。
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    #: passive_deletes=True 讓刪除交由資料庫的 ON DELETE CASCADE 執行，
    #: 不逐筆載入子資料。DB 層 cascade 使「殘留無主餐點」在結構上不可能
    #: 發生（FR-040），而非依賴應用層記得先刪。
    menu_items: Mapped[list["MenuItem"]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def has_coordinates(self) -> bool:
        """後台清單據此標示待補座標的店家（FR-025）。"""
        return self.latitude is not None and self.longitude is not None


__all__ = ["Store"]
