"""後台店家維護端點（spec US2）。

權限檢查掛在 router 建構參數上（research.md R-02）——這樣新增端點時不可能
忘記加，也不需在各端點內重複手寫角色判斷（憲章「架構約束」）。

route_class 讓驗證錯誤回傳統一的錯誤信封，範圍限縮在管理端，不影響第一輪
既有端點（見 admin_route.py）。
"""

import uuid

from fastapi import APIRouter, Depends, Response, status

from app.api.v1.admin_route import AdminAPIRoute
from app.core.deps import DbSession, require_admin
from app.schemas.admin import StoreInput, StoreListOut, StoreOut, StorePatch, StoreWithCountOut
from app.services import admin_stores

router = APIRouter(
    prefix="/admin/stores",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
    route_class=AdminAPIRoute,
)


@router.get("", response_model=StoreListOut)
def list_stores(db: DbSession) -> StoreListOut:
    """店家清單，每筆附餐點數。

    餐點數同時服務兩個用途：清單上讓管理員看出資料完整度，以及刪除確認
    提示中的「將一併刪除 N 道餐點」（FR-038）。
    """
    rows = admin_stores.list_stores(db)
    return StoreListOut(
        stores=[
            StoreWithCountOut(**StoreOut.model_validate(store).model_dump(), menu_item_count=count)
            for store, count in rows
        ]
    )


@router.post("", response_model=StoreOut, status_code=status.HTTP_201_CREATED)
def create_store(payload: StoreInput, db: DbSession) -> StoreOut:
    store = admin_stores.create_store(db, payload)
    return StoreOut.model_validate(store)


@router.get("/{store_id}", response_model=StoreOut)
def get_store(store_id: uuid.UUID, db: DbSession) -> StoreOut:
    return StoreOut.model_validate(admin_stores.get_store(db, store_id))


@router.patch("/{store_id}", response_model=StoreOut)
def update_store(store_id: uuid.UUID, payload: StorePatch, db: DbSession) -> StoreOut:
    return StoreOut.model_validate(admin_stores.update_store(db, store_id, payload))


@router.delete("/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_store(store_id: uuid.UUID, db: DbSession) -> Response:
    """刪除店家，連帶刪除其所有餐點（FR-037）。"""
    admin_stores.delete_store(db, store_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
