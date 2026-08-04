"""店家與餐點查詢（第二輪，推薦餐廳模組）。

⚠️ 本檔案只能有 GET
====================
新增／修改／刪除店家與餐點屬**第三輪管理員後台**的範圍。本輪不實作也
**不預留**寫入端點（spec FR-029），避免與第三輪重複或衝突。
此約束由 tests/integration/test_stores_readonly.py 以 OpenAPI schema 斷言。

⚠️ 不依入口分岔
================
推薦餐廳的 UI 僅於 LIFF 提供，但那是**功能範圍**的界定（哪個入口實作這個
畫面），不是安全邊界。後端對所有已登入使用者一視同仁，不檢查來源入口、
不存在 LIFF 專屬端點——憲章原則 III 與「架構約束」要求 API 契約對四端一致
（research.md R-03）。

⚠️ 憲章原則 V
==============
本模組的營養數值一律來自 menu_items，不查詢 /foods/* 或通用食物營養對照表。
"""

import uuid

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.core.errors import AppError
from app.schemas.store import (
    MenuItemListResponse,
    MenuItemOut,
    StoreListResponse,
    StoreOut,
)
from app.services import stores as stores_service

router = APIRouter(prefix="/stores", tags=["stores"])


def _to_store_out(store, distance_m: int | None) -> StoreOut:
    return StoreOut(
        id=store.id,
        name=store.name,
        address=store.address,
        latitude=store.latitude,
        longitude=store.longitude,
        distance_m=distance_m,
    )


@router.get("", response_model=StoreListResponse)
def list_stores(
    db: DbSession,
    user: CurrentUser,  # noqa: ARG001 — 僅用於要求登入（FR-004）
    lat: float | None = Query(default=None, ge=-90, le=90, description="使用者目前緯度"),
    lng: float | None = Query(default=None, ge=-180, le=180, description="使用者目前經度"),
) -> StoreListResponse:
    """店家清單。

    同時提供 lat 與 lng → **附近模式**：5 公里內、依距離排序、最多 10 家。
    兩者皆省略 → **全部模式**：全部店家、依名稱排序、不含距離。

    ⚠️ 只提供其中一個必須回 422，**不得無聲退回全部模式**——否則前端會
    誤以為使用者的位置已納入計算，而實際上看到的是未排序的清單
    （research.md R-06）。
    """
    if (lat is None) != (lng is None):
        raise AppError(
            "VALIDATION_ERROR",
            message="緯度與經度必須同時提供或同時省略。",
        )

    mode, radius_km, total, pairs = stores_service.list_stores(db, lat, lng)
    return StoreListResponse(
        mode=mode,
        radius_km=radius_km,
        total_store_count=total,
        stores=[_to_store_out(store, distance_m) for store, distance_m in pairs],
    )


@router.get("/{store_id}", response_model=StoreOut)
def get_store(
    db: DbSession,
    user: CurrentUser,  # noqa: ARG001 — 僅用於要求登入
    store_id: uuid.UUID,
) -> StoreOut:
    """單一店家。

    店家不存在時回 404——刪除為實刪除，使用者停留期間店家可能已被第三輪
    後台移除，前端據此顯示「此店家已不存在」與返回操作（FR-027）。
    """
    store = stores_service.get_store(db, store_id)
    # 此端點不接受座標，distance_m 恆為 None（代表「未計算」而非距離為 0）。
    return _to_store_out(store, None)


@router.get("/{store_id}/menu-items", response_model=MenuItemListResponse)
def list_menu_items(
    db: DbSession,
    user: CurrentUser,  # noqa: ARG001 — 僅用於要求登入
    store_id: uuid.UUID,
) -> MenuItemListResponse:
    """店家的餐點清單。

    空陣列代表該店尚未登錄餐點，屬**正常結果**——回 200 而非 404，由前端
    顯示空狀態說明（FR-024）。

    營養欄位原樣回傳 None 與 0，**不做任何正規化**：None 代表店家未提供
    （前端顯示「無資料」），0 代表店家登錄為零（前端顯示 0）。兩者對使用者
    的意義不同（FR-025）。
    """
    items = stores_service.list_menu_items(db, store_id)
    return MenuItemListResponse(
        menu_items=[
            MenuItemOut(
                id=item.id,
                store_id=item.store_id,
                name=item.name,
                # 資料表欄位為 calories（共用契約），API 欄位沿用第一輪的
                # calories_kcal 命名慣例——轉換只發生在這一層。
                calories_kcal=item.calories,
                protein_g=item.protein_g,
                carbs_g=item.carbs_g,
                fat_g=item.fat_g,
            )
            for item in items
        ]
    )
