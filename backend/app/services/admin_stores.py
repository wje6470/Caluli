"""後台店家維護的業務邏輯。

★ 檔名為何不是 stores.py
========================
第二輪（推薦餐廳）已規劃 `services/stores.py` 存放使用者端的查詢管線。
兩個分支共用同一張資料表但操作方向相反，同檔名會在合併時造成硬衝突，
故寫入端改用 admin_ 前綴。讀取端擁有 stores.py，寫入端擁有本檔。

★ 查無資料一律 NOT_FOUND
========================
不回傳 None 讓呼叫端自行判斷——那會讓「忘記檢查」變成可能，且各端點的
錯誤訊息容易長得不一樣。統一在此 raise，端點層只處理成功路徑。
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import MenuItem, Store
from app.schemas.admin import StoreInput, StorePatch


def _get_or_404(db: Session, store_id: uuid.UUID) -> Store:
    store = db.get(Store, store_id)
    if store is None:
        # 可能已被另一位管理員刪除（FR-028）。明確回報，讓前端能提示
        # 管理員重新載入清單，而不是顯示通用錯誤或靜默失敗。
        raise AppError("NOT_FOUND")
    return store


def list_stores(db: Session) -> list[tuple[Store, int]]:
    """回傳 (店家, 餐點數) 的清單。

    以 LEFT OUTER JOIN + GROUP BY 一次算出餐點數，避免 N+1 查詢。
    餐點數供清單顯示與刪除確認提示使用（FR-038），故不另開一支端點——
    管理員按下刪除時不需要再等一次往返。
    """
    statement = (
        select(Store, func.count(MenuItem.id))
        .outerjoin(MenuItem, MenuItem.store_id == Store.id)
        .group_by(Store.id)
        .order_by(Store.created_at.desc())
    )
    return [(store, count) for store, count in db.execute(statement).all()]


def get_store(db: Session, store_id: uuid.UUID) -> Store:
    return _get_or_404(db, store_id)


def create_store(db: Session, payload: StoreInput) -> Store:
    store = Store(
        name=payload.name.strip(),
        address=payload.address.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(store)
    db.flush()
    db.refresh(store)
    return store


def update_store(db: Session, store_id: uuid.UUID, payload: StorePatch) -> Store:
    """部分更新。

    ★ 座標的成對規則必須以「套用後的最終狀態」判定（FR-022）
    ======================================================
    這是本函式唯一容易寫錯的地方。若只檢查本次請求帶了哪些欄位，
    以下情境會漏掉：

        原本 lat=25, lng=121，只送 {"latitude": null}
        → 本次請求「只改了一個欄位」，看似無害
        → 但套用後變成 lat=NULL, lng=121，不成對

    故必須先算出最終值再驗證。資料庫的 CHECK 約束會兜底，但那會拋出
    IntegrityError 而非可讀的訊息，所以這層仍要擋。
    """
    store = _get_or_404(db, store_id)
    provided = payload.model_fields_set

    # 未提供的欄位維持原值；明確傳入 null 才是「清除」。
    final_latitude = payload.latitude if "latitude" in provided else store.latitude
    final_longitude = payload.longitude if "longitude" in provided else store.longitude

    if (final_latitude is None) != (final_longitude is None):
        raise AppError(
            "VALIDATION_ERROR",
            message="緯度與經度必須同時填寫，或同時留空。",
        )

    if "name" in provided and payload.name is not None:
        store.name = payload.name.strip()
    if "address" in provided and payload.address is not None:
        store.address = payload.address.strip()
    store.latitude = final_latitude
    store.longitude = final_longitude

    db.flush()
    db.refresh(store)
    return store


def delete_store(db: Session, store_id: uuid.UUID) -> None:
    """刪除店家。

    其底下的餐點由資料庫的 ON DELETE CASCADE 一併移除（FR-037、FR-040）——
    不在此逐筆刪除，讓「殘留無主餐點」在結構上不可能發生，而非依賴這裡
    記得處理。

    二次確認由前端負責（FR-038）：後端不提供「預覽將刪除幾筆」的端點，
    該數量取自清單既有的 menu_item_count。
    """
    store = _get_or_404(db, store_id)
    db.delete(store)
    db.flush()
