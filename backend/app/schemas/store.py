"""店家與餐點的請求／回應模型（第二輪）。

對齊 specs/002-restaurant-recommendation/contracts/openapi.yaml。

⚠️ 欄位命名的一處刻意落差
==========================
資料表欄位名為 `calories`（共用契約所定，不可更動），但 API 回應欄位名為
`calories_kcal`——沿用第一輪 per_100g 系列的命名慣例，讓前端在兩個模組間
看到一致的單位標示。轉換只發生在本層，資料層與契約皆不受影響。

⚠️ 數值欄位一律宣告為 float，**不可用 Decimal**
================================================
Pydantic v2 會把 `Decimal` 序列化成 JSON **字串**（`"650.00"`）以保留精度，
但 contracts/openapi.yaml 宣告的是 `type: number`，前端型別也是 `number`。
用 Decimal 會讓實際 wire format 與已發布的契約不符，前端拿到字串後任何
`value.toFixed()` 都會拋 TypeError——這個 bug 實際發生過。

營養值與經緯度都不需要十進位精度（NUMERIC(7,2) / NUMERIC(9,6) 的有效位數
遠低於 float64 的 ~15-17 位），因此 float 是正確且無損的選擇。
資料層仍是 Decimal，轉換只發生在本層。

tests/integration/test_stores_api.py 有斷言守著 JSON 型別，防止改回 Decimal。
"""

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class StoreOut(BaseModel):
    id: uuid.UUID
    #: 店名不具唯一性（連鎖分店同名），客戶端不得以此識別或去重（FR-016a）。
    name: str
    #: 分辨同名分店的唯一依據，清單必須顯示（FR-016）。
    address: str | None
    latitude: float | None
    longitude: float | None
    #: 與使用者當次座標的直線距離（公尺，四捨五入）。
    #: None 代表「未計算」（全部模式或單一店家查詢），**不代表距離為 0**。
    distance_m: int | None = None


class StoreListResponse(BaseModel):
    #: 由是否提供座標決定，非客戶端指定。
    mode: Literal["nearby", "all"]
    #: 附近模式所套用的半徑上限；全部模式為 None。
    radius_km: float | None
    #: 資料庫中的店家總數，**不受**半徑、筆數上限或座標有效性影響。
    #:
    #: 前端用它區分兩種語意完全不同的空狀態（research.md R-05）：
    #:   stores 空 + total > 0  → 「附近查無店家」，提供「改看全部店家」
    #:   stores 空 + total == 0 → 「目前尚無店家資料」，不提供改看操作
    #: 少了這個欄位，前端只看 stores: [] 無從分辨，而後者提供改看按鈕
    #: 只會導向另一個空清單。
    total_store_count: int = Field(ge=0)
    stores: list[StoreOut]


class MenuItemOut(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    name: str

    # ------------------------------------------------------------------
    # 四個營養欄位皆為 Decimal | None，且 None 與 0 **不得互相正規化**：
    #   None → 店家未提供 → 前端顯示「無資料」
    #   0    → 店家登錄為零 → 前端顯示 0
    # 兩者對使用者的意義不同（FR-025）。
    # ------------------------------------------------------------------
    calories_kcal: float | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None


class MenuItemListResponse(BaseModel):
    #: 空陣列代表該店尚未登錄餐點，屬**正常結果而非錯誤**（FR-024）——
    #: 端點回 200 而非 404，前端顯示空狀態說明。
    menu_items: list[MenuItemOut]
