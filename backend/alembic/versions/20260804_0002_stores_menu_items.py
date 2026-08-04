"""stores + menu_items — 第三輪後台維護的資料表

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-04

================================================================================
共用契約
================================================================================
本 migration 建立的兩張表由**第二輪（推薦餐廳，讀取端）與第三輪（後台維護，
寫入端）共用**，欄位結構完全依 reference/shared-schema-store-menu.md，
未自行增減或更名任何欄位。

依 2026-08-04 雙方議定的「由先合併回 main 的一方建表」，本輪先行建立。
第二輪若已產生自己的建表 migration，合併前須刪除，否則會出現：
  - Alembic 雙 head（兩支都以 0001 為 down_revision）→ upgrade 直接失敗
  - relation already exists（兩支都 create_table 同兩張表）

建表前已確認的三項欄位決議（原契約未載明）：
  1. 主鍵型別        UUID + gen_random_uuid()
  2. 四個營養欄位     **nullable**（NULL = 店家未提供，0 = 確實為零）
  3. name 欄位型別    VARCHAR(255)

================================================================================
憲章原則 V 稽核紀錄（tasks.md T008）
================================================================================
檢查日期：2026-08-04

1. 本 migration 建立的資料表共 2 張：stores、menu_items。
   兩者皆屬「特定店家／餐點之營養值」體系。

2. 出向外鍵檢查：
     - stores      ：無出向外鍵
     - menu_items  ：僅 store_id → stores.id（同體系內部，ON DELETE CASCADE）
   **兩張表皆未指向 food_nutrition_references、meal_items 或任何第一輪的
   營養／紀錄資料表。**

3. 入向外鍵檢查：第一輪的 6 張表無任何一張指向 stores 或 menu_items
   （本 migration 不修改既有表）。

4. 未以型別／分類欄位在單一表內混存兩類營養資料：menu_items 只存店家餐點；
   通用食物營養值仍獨立存於 food_nutrition_references，兩者的寫入來源與
   查詢路徑完全分離。

5. 數值不互相參照：即使 menu_items.name 與 food_nutrition_references.name
   字面相同（例如兩邊都有「滷肉飯」），系統不查詢、不比對、不同步、
   不以其一覆寫另一（spec FR-041）。

結論：符合憲章原則 V（營養資料表分離）。

================================================================================
對第一輪的影響
================================================================================
upgrade() 只有 create_table 與 create_index，**不含任何 alter_table**，
故對第一輪既有的 6 張表零風險（spec FR-043）。
================================================================================
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stores",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # 不設 UNIQUE：連鎖分店同名為正常資料，以 address 區分（FR-027）。
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=False),
        # 座標選填（FR-021），且必須成對（FR-022）。
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)", name="ck_stores_coords_paired"
        ),
        sa.CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_stores_latitude_range",
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_stores_longitude_range",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "menu_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        # 四個營養欄位皆 nullable：NULL = 店家未提供，0 = 確實為零。
        # 兩者語意不同，寫入端不得以 0 代替 NULL。
        sa.Column("calories", sa.Numeric(precision=7, scale=2), nullable=True),
        sa.Column("protein_g", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("carbs_g", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("fat_g", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("calories >= 0", name="ck_menu_items_calories"),
        sa.CheckConstraint("protein_g >= 0", name="ck_menu_items_protein"),
        sa.CheckConstraint("carbs_g >= 0", name="ck_menu_items_carbs"),
        sa.CheckConstraint("fat_g >= 0", name="ck_menu_items_fat"),
        # ★ CASCADE 讓「殘留無所屬店家的餐點」在結構上不可能發生（FR-040），
        #   而非依賴應用層記得先刪子資料。
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_menu_items_store", "menu_items", ["store_id"])


def downgrade() -> None:
    op.drop_index("ix_menu_items_store", table_name="menu_items")
    op.drop_table("menu_items")
    op.drop_table("stores")
