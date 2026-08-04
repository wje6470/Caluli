"""管理端 schemas（對應 specs/003-admin-backoffice/contracts/admin-api.yaml）。

欄位名稱逐字沿用 reference/shared-schema-store-menu.md，**不加單位後綴**
（即使第一輪的 meal_items 用的是 calories_kcal）——契約優先於內部命名
一致性，因為這組欄位由第二輪共用。

驗證採雙層（沿用第一輪慣例）：此層負責產生可讀的中文錯誤訊息，
資料庫的 CHECK 約束負責兜底。
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _latitude() -> object:
    """每次呼叫產生新的 FieldInfo——pydantic v2 不應跨模型共用同一個實例。"""
    return Field(default=None, ge=-90, le=90, description="緯度，須與經度成對")


def _longitude() -> object:
    return Field(default=None, ge=-180, le=180, description="經度，須與緯度成對")


class AdminSessionOut(BaseModel):
    """管理員身分確認的回應。

    刻意只有三個欄位——前端守衛只需要知道「你是管理員」。不放 LINE
    憑證、不放管理員名單、不放權限細目，避免擴大暴露面。
    """

    user_id: uuid.UUID
    display_name: str | None = None
    #: 非管理員到不了這支端點，故型別上就只可能是 admin。
    role: Literal["admin"]


# ─── 店家 ────────────────────────────────────────────────────────────


class StoreInput(BaseModel):
    """新增店家。座標選填但須成對（FR-021、FR-022）。"""

    name: str = Field(min_length=1, max_length=255)
    address: str = Field(min_length=1, max_length=500)
    latitude: Decimal | None = _latitude()
    longitude: Decimal | None = _longitude()

    @model_validator(mode="after")
    def _validate(self) -> "StoreInput":
        # 只有空白的字串在 min_length 檢查中會通過，須另外擋。
        if not self.name.strip():
            raise ValueError("店家名稱不得為空白。")
        if not self.address.strip():
            raise ValueError("地址不得為空白。")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("緯度與經度必須同時填寫，或同時留空。")
        return self


class StorePatch(BaseModel):
    """編輯店家。未提供的欄位維持原值。

    ⚠️ 座標的成對規則**不能在此驗證**——本 schema 只看得到本次請求帶了
    什麼，看不到套用後的最終狀態。例如原本有完整座標、只送 latitude=null，
    在此看起來只是「改了一個欄位」，實際卻會造成不成對。
    故成對檢查放在 service 層（見 services/admin_stores.py 的 update_store）。
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = Field(default=None, min_length=1, max_length=500)
    latitude: Decimal | None = _latitude()
    longitude: Decimal | None = _longitude()

    @model_validator(mode="after")
    def _validate(self) -> "StorePatch":
        if self.name is not None and not self.name.strip():
            raise ValueError("店家名稱不得為空白。")
        if self.address is not None and not self.address.strip():
            raise ValueError("地址不得為空白。")
        return self


class StoreOut(BaseModel):
    """★ 回應的數值欄位型別為 `float`，不是 `Decimal`（2026-08-04 雙方定案）

    Decimal 在 pydantic v2 會序列化成**字串**（"25.039600"），而契約與四端的
    型別宣告都是 JSON number。三個理由讓 float 勝出：

      1. string 的精度優勢在本專案不成立——每個消費端拿到值第一件事就是轉
         float 顯示或計算，只是把轉換往後推。
      2. 憲章原則 III 要求四端呼叫同一組 API 且契約一致；Dart／Swift 端遇到
         字串得對每個數值欄位 parse，成本乘以客戶端數量。
      3. 精度無損：NUMERIC(9,6) 最多 9 位有效數字、NUMERIC(7,2) 最多 7 位，
         都遠低於 float64 的 ~15–17 位。

    ⚠️ 改回 Decimal 會靜默破壞所有客戶端。test_admin_stores.py 有
       isinstance 斷言擋著——用 float(x) 比較是擋不住的，字串也會通過。
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str
    #: null 代表未設定座標——該店家不會出現在第二輪依距離排序的結果中。
    latitude: float | None
    longitude: float | None
    created_at: datetime
    updated_at: datetime


class StoreWithCountOut(StoreOut):
    #: 供清單顯示與刪除確認提示使用（FR-038），前端無需額外請求。
    menu_item_count: int


class StoreListOut(BaseModel):
    stores: list[StoreWithCountOut]


# ─── 餐點 ────────────────────────────────────────────────────────────
#
# 欄位名稱逐字沿用共用契約（calories、protein_g…），**不加單位後綴**，
# 即使第一輪的 meal_items 用的是 calories_kcal——契約優先於內部命名一致性。
#
# 四個營養欄位皆選填：
#     未提供 / null = 店家未提供此項數值
#     0             = 該項確實為零
# 兩者語意不同，服務層不得以 0 代替 null 寫入（FR-032）。


def _nutrition(description: str) -> object:
    return Field(default=None, ge=0, description=f"{description}；null 代表店家未提供，與 0 不同")


class MenuItemInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    calories: Decimal | None = _nutrition("熱量（大卡）")
    protein_g: Decimal | None = _nutrition("蛋白質（公克）")
    carbs_g: Decimal | None = _nutrition("碳水化合物（公克）")
    fat_g: Decimal | None = _nutrition("脂肪（公克）")

    @model_validator(mode="after")
    def _validate(self) -> "MenuItemInput":
        if not self.name.strip():
            raise ValueError("餐點名稱不得為空白。")
        return self


class MenuItemPatch(BaseModel):
    """部分更新。

    ⚠️ 「未提供該欄位」與「明確傳入 null」是兩件不同的事：
        未提供      → 維持原值
        明確傳 null → 改為「未提供」
    兩者在 pydantic 中都是 None，故服務層必須以 `model_fields_set` 區分，
    不能以值是否為 None 判斷。
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    calories: Decimal | None = _nutrition("熱量（大卡）")
    protein_g: Decimal | None = _nutrition("蛋白質（公克）")
    carbs_g: Decimal | None = _nutrition("碳水化合物（公克）")
    fat_g: Decimal | None = _nutrition("脂肪（公克）")

    @model_validator(mode="after")
    def _validate(self) -> "MenuItemPatch":
        if self.name is not None and not self.name.strip():
            raise ValueError("餐點名稱不得為空白。")
        return self


class MenuItemOut(BaseModel):
    """數值欄位為 `float` 的理由同 StoreOut。

    null 仍是 JSON null（不是字串），故「未提供」與「0」在型別上依然
    直接可分——這點不受本次型別調整影響。
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    name: str
    #: null = 店家未提供，**不是 0**。呈現時必須區分（FR-033）。
    calories: float | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    created_at: datetime
    updated_at: datetime


class MenuItemListOut(BaseModel):
    menu_items: list[MenuItemOut]
