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
from app.schemas.admin import MenuItemInput, MenuItemPatch, StoreInput, StorePatch


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


# ─── 餐點 ────────────────────────────────────────────────────────────

#: 可由客戶端寫入的營養欄位。集中一處，避免各函式各寫一份而漏掉某欄。
NUTRITION_FIELDS = ("calories", "protein_g", "carbs_g", "fat_g")


def _get_menu_item_or_404(db: Session, menu_item_id: uuid.UUID) -> MenuItem:
    item = db.get(MenuItem, menu_item_id)
    if item is None:
        raise AppError("NOT_FOUND")
    return item


def list_menu_items(db: Session, store_id: uuid.UUID) -> list[MenuItem]:
    """列出某店家的餐點。

    先確認店家存在，讓「店家不存在」與「店家存在但沒有餐點」得到不同的
    回應——前者是 404，後者是空清單加空狀態畫面（FR-036）。若省略這步，
    兩者都會回空清單，管理員無從分辨。

    查詢一律以 store_id 收斂，不存在「查全部再過濾」的路徑（FR-033）。
    """
    _get_or_404(db, store_id)
    statement = select(MenuItem).where(MenuItem.store_id == store_id).order_by(MenuItem.created_at)
    return list(db.scalars(statement).all())


def create_menu_item(db: Session, store_id: uuid.UUID, payload: MenuItemInput) -> MenuItem:
    """在指定店家底下新增餐點。

    店家不存在時在此擋下（FR-035）——若放任寫入，外鍵會擋，但錯誤訊息
    是資料庫層的 IntegrityError，對管理員毫無意義。

    ⚠️ 未提供的營養欄位寫入 None 而非 0：以 0 代替會讓「店家未提供」與
       「確實為 0」的區別在寫入當下永久喪失（FR-032）。
    """
    _get_or_404(db, store_id)

    item = MenuItem(
        store_id=store_id,
        name=payload.name.strip(),
        **{field: getattr(payload, field) for field in NUTRITION_FIELDS},
    )
    db.add(item)
    db.flush()
    db.refresh(item)
    return item


def update_menu_item(db: Session, menu_item_id: uuid.UUID, payload: MenuItemPatch) -> MenuItem:
    """部分更新餐點。

    ★ 以 model_fields_set 判斷欄位是否被提供，而非以值是否為 None
    ================================================================
        未提供該欄位   → 維持原值
        明確傳入 null  → 改為「未提供」（例如發現先前登錄有誤）

    兩者在 pydantic 中的值都是 None，用 `if payload.calories is not None`
    判斷會讓「清除數值」變成不可能的操作。

    所屬店家不可變更——契約沒有「把餐點移到別家店」的語意，故 store_id
    不在可更新欄位內。
    """
    item = _get_menu_item_or_404(db, menu_item_id)
    provided = payload.model_fields_set

    if "name" in provided and payload.name is not None:
        item.name = payload.name.strip()

    for field in NUTRITION_FIELDS:
        if field in provided:
            setattr(item, field, getattr(payload, field))

    db.flush()
    db.refresh(item)
    return item


def delete_menu_item(db: Session, menu_item_id: uuid.UUID) -> None:
    """刪除單一餐點。店家本身與其餘餐點不受影響（FR-030）。"""
    item = _get_menu_item_or_404(db, menu_item_id)
    db.delete(item)
    db.flush()
