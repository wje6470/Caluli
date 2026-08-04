"""店家與餐點查詢（第二輪）。

⚠️ 憲章原則 V — 本模組不得 import 第一輪的營養相關模組
========================================================
營養值一律取自 menu_items。即使餐點名稱與通用食物營養對照表
（food_nutrition_references）中的食物同名，也**不查詢、不連動、不以任一方
的數值替代另一方**（spec FR-030、FR-031）。

此約束由 tests/integration/test_nutrition_isolation.py 以靜態檢查斷言——
若哪天這裡出現 `from app.db.models import FoodNutritionReference`，測試會失敗。

⚠️ 無軟刪除過濾
================
資料表沒有 deleted_at／is_active 欄位，刪除為實刪除（2026-08-04 交接確認）。
因此本模組的查詢**不得**加任何「排除已刪除」的條件（spec FR-018a）——那會
成為未來每支查詢都可能漏加的過濾條件。
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import MenuItem, Store
from app.services.geo import haversine_km


def _has_valid_coords(store: Store) -> bool:
    """座標是否可用於距離計算。

    寫入端（第三輪）保證緯度與經度同時有值或同時為 NULL，但這裡仍做防禦性
    檢查——成本為零，且讓本函式的正確性不依賴另一個分支的行為。
    """
    return store.latitude is not None and store.longitude is not None


def list_stores(
    db: Session,
    lat: float | None = None,
    lng: float | None = None,
) -> tuple[str, float | None, int, list[tuple[Store, int | None]]]:
    """店家清單。回傳 (mode, radius_km, total_store_count, [(store, distance_m)])。

    ⚠️ 附近模式的處理順序固定，**不可調換**（data-model.md「查詢管線」）：

        1. 取出全部 stores
        2. 排除座標為 NULL 者                      ← FR-018
        3. 對其餘每筆計算 haversine 距離
        4. 過濾 distance > nearby_radius_km        ← FR-020
        5. 依距離升冪排序                          ← FR-014
        6. 取前 nearby_limit 筆                    ← FR-014
        7. 附上 total_store_count（步驟 1 的總數）  ← FR-019 / R-05

    三個易錯點：
      * 步驟 4 早於 6——先取 10 筆再過濾半徑會得到錯誤的少於 10 筆結果；
        反之亦不可先截斷。
      * 步驟 2 早於 3——NULL 座標若未先排除，會使計算失敗或被當作 (0,0)
        而排到最前面。
      * 步驟 7 的計數取自步驟 1，**未經任何過濾**——它要回答的是「資料庫
        裡到底有沒有店家」，不是「附近有幾家」。
    """
    settings = get_settings()

    # 步驟 1：取出全部（不加任何軟刪除過濾，見模組 docstring）。
    all_stores = list(db.scalars(select(Store)).all())
    total_store_count = len(all_stores)

    # 全部模式：無座標輸入時依名稱升冪，距離一律 None（FR-017）。
    if lat is None or lng is None:
        ordered = sorted(all_stores, key=lambda s: (s.name, str(s.id)))
        return "all", None, total_store_count, [(s, None) for s in ordered]

    # 步驟 2＋3：排除無效座標後計算距離。
    with_distance: list[tuple[Store, float]] = []
    for store in all_stores:
        if not _has_valid_coords(store):
            continue
        distance_km = haversine_km(lat, lng, float(store.latitude), float(store.longitude))
        with_distance.append((store, distance_km))

    # 步驟 4：半徑過濾。
    within = [pair for pair in with_distance if pair[1] <= settings.nearby_radius_km]

    # 步驟 5：依距離升冪（同距離時以 id 穩定排序，避免結果順序浮動）。
    within.sort(key=lambda pair: (pair[1], str(pair[0].id)))

    # 步驟 6：取前 N 筆。範圍內不足 N 家時回傳實際筆數，
    # **不以範圍外的店家補足**（FR-020 明文禁止）。
    limited = within[: settings.nearby_limit]

    return (
        "nearby",
        settings.nearby_radius_km,
        total_store_count,
        [(store, round(distance_km * 1000)) for store, distance_km in limited],
    )


def get_store(db: Session, store_id: uuid.UUID) -> Store:
    """單一店家。不存在時拋 NOT_FOUND（FR-027）。

    店家可能在使用者停留期間被第三輪後台實刪除，此路徑是常態而非異常。
    """
    store = db.get(Store, store_id)
    if store is None:
        raise AppError("NOT_FOUND")
    return store


def list_menu_items(db: Session, store_id: uuid.UUID) -> list[MenuItem]:
    """某店家的全部餐點。

    店家不存在時拋 NOT_FOUND；店家存在但沒有餐點時回**空清單**——那是正常
    結果而非錯誤（FR-024），端點據此回 200 並由前端顯示空狀態。

    不去重：同店家內允許同名餐點（2026-08-04 交接確認）。
    """
    get_store(db, store_id)  # 不存在則在此拋出，避免回空清單而誤導前端
    return list(
        db.scalars(
            select(MenuItem)
            .where(MenuItem.store_id == store_id)
            .order_by(MenuItem.name, MenuItem.id)
        ).all()
    )
