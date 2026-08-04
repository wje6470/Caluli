"""店家（stores）— 與第三輪管理員後台共用。

═══════════════════════════════════════════════════════════════════
⚠️ 合併時以**第三輪（feature/round3-admin）的版本為準**，本檔可直接覆蓋
═══════════════════════════════════════════════════════════════════
依 2026-08-04 第三輪執行清單，`stores` / `menu_items` 兩張表由第三輪建立
（他們負責寫入，本輪只讀）。本檔存在的唯一理由是讓第二輪分支在合併前
仍能獨立執行測試與 seed——欄位定義**逐欄比照第三輪的最終定義**，因此
合併時直接採用對方版本即可，本輪的查詢程式碼不需要任何改動。

本輪依賴的是 `from app.db.models import Store, MenuItem` 這個匯入介面，
第三輪已保證該介面穩定，與檔案怎麼切無關。

⚠️ 憲章原則 V — 資料表分離
====================================
`MenuItem`（見 menu_item.py）是「特定店家／餐點之營養值」，與第一輪的
`FoodNutritionReference`（拍照辨識用之通用食物營養對照表）是**兩套完全
獨立的資料**：禁止任何方向的外鍵、禁止合併、禁止以型別欄位混存。即使
餐點名稱與通用對照表中的食物同名，也一律採用店家自行登錄的數值
（spec FR-030、FR-031）。

第三輪保證的三件事（本輪的查詢據此設計）：
  1. 不會出現只有緯度沒有經度的店家（DB CHECK ＋ 寫入端擋掉）
  2. 不會殘留無所屬店家的餐點（DB 層 ON DELETE CASCADE）
  3. NULL 營養值不會被寫成 0（對方有測試專門斷言）
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
    """收錄的餐飲店家。本輪唯讀；寫入由第三輪管理員後台負責（FR-029）。"""

    __tablename__ = "stores"
    __table_args__ = (
        # 保證經緯度成對存在或成對為 NULL——第三輪於 DB 層強制，
        # 本輪的 _has_valid_coords() 仍保留防禦性檢查（成本為零）。
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name="ck_stores_coords_paired",
        ),
        CheckConstraint(
            "latitude IS NULL OR (latitude BETWEEN -90 AND 90)",
            name="ck_stores_latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude BETWEEN -180 AND 180)",
            name="ck_stores_longitude_range",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    #: 店家名稱。**刻意不設 UNIQUE**——連鎖分店同名是正常資料（FR-016a）。
    #: 任何以 name 作為識別鍵的程式碼都是錯的，一律用 id。
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    #: 地址。**NOT NULL**（第三輪 2026-08-04 定義）——它是分辨同名分店的
    #: 唯一依據，故清單必須顯示（FR-016）。系統不驗證其與座標是否一致；
    #: 距離一律以座標為準。
    address: Mapped[str] = mapped_column(String(500), nullable=False)

    #: 經緯度為**選填**——後台允許只建「名稱＋地址」、暫不填座標的店家，
    #: 故 NULL 是常態資料而非異常。無座標的店家不參與距離計算與排序
    #: （FR-018），但在不排序的全部店家清單中正常出現。
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    menu_items: Mapped[list["MenuItem"]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
