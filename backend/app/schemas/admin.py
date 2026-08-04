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
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str
    #: null 代表未設定座標——該店家不會出現在第二輪依距離排序的結果中。
    latitude: Decimal | None
    longitude: Decimal | None
    created_at: datetime
    updated_at: datetime


class StoreWithCountOut(StoreOut):
    #: 供清單顯示與刪除確認提示使用（FR-038），前端無需額外請求。
    menu_item_count: int


class StoreListOut(BaseModel):
    stores: list[StoreWithCountOut]
