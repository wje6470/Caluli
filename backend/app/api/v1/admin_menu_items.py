"""後台餐點維護端點（spec US3）。

路徑分兩組，刻意如此：

    POST/GET  /admin/stores/{store_id}/menu-items   建立與列出——需要店家脈絡
    PATCH/DELETE /admin/menu-items/{menu_item_id}   編輯與刪除——以餐點自身定位

編輯與刪除不帶 store_id，因為**餐點的歸屬不可變更**：共用契約沒有「把餐點
移到別家店」的語意。若路徑帶上 store_id，等於暗示它可以是別的值，也讓
「store_id 與 menu_item_id 不匹配」變成需要額外處理的情境。

權限與驗證錯誤的處理方式同 admin_stores.py。
"""

import uuid

from fastapi import APIRouter, Depends, Response, status

from app.api.v1.admin_route import AdminAPIRoute
from app.core.deps import DbSession, require_admin
from app.schemas.admin import MenuItemInput, MenuItemListOut, MenuItemOut, MenuItemPatch
from app.services import admin_stores

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
    route_class=AdminAPIRoute,
)


@router.get("/stores/{store_id}/menu-items", response_model=MenuItemListOut)
def list_menu_items(store_id: uuid.UUID, db: DbSession) -> MenuItemListOut:
    """列出該店家的餐點。

    店家不存在回 404；店家存在但沒有餐點回空清單——兩者是不同狀態，
    前端據此分別呈現錯誤與空狀態（FR-036）。
    """
    items = admin_stores.list_menu_items(db, store_id)
    return MenuItemListOut(menu_items=[MenuItemOut.model_validate(item) for item in items])


@router.post(
    "/stores/{store_id}/menu-items",
    response_model=MenuItemOut,
    status_code=status.HTTP_201_CREATED,
)
def create_menu_item(store_id: uuid.UUID, payload: MenuItemInput, db: DbSession) -> MenuItemOut:
    item = admin_stores.create_menu_item(db, store_id, payload)
    return MenuItemOut.model_validate(item)


@router.patch("/menu-items/{menu_item_id}", response_model=MenuItemOut)
def update_menu_item(menu_item_id: uuid.UUID, payload: MenuItemPatch, db: DbSession) -> MenuItemOut:
    item = admin_stores.update_menu_item(db, menu_item_id, payload)
    return MenuItemOut.model_validate(item)


@router.delete("/menu-items/{menu_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu_item(menu_item_id: uuid.UUID, db: DbSession) -> Response:
    admin_stores.delete_menu_item(db, menu_item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
