"""飲食紀錄端點。"""

import uuid
from datetime import date

from fastapi import APIRouter, Query, Response, status

from app.core.clock import today
from app.core.deps import CurrentUser, DbSession
from app.core.errors import AppError
from app.schemas.meal_record import MealRecordInput, MealRecordListResponse, MealRecordOut
from app.services import meal_records
from app.services.photo_storage import get_photo_storage

router = APIRouter(prefix="/meal-records", tags=["records"])


@router.get("", response_model=MealRecordListResponse)
def list_meal_records(
    db: DbSession, user: CurrentUser, on_date: date | None = Query(default=None, alias="date")
) -> MealRecordListResponse:
    records = meal_records.list_records(db, user.id, on_date or today())
    return MealRecordListResponse(records=[meal_records.to_out(r) for r in records])


@router.post("", response_model=MealRecordOut, status_code=status.HTTP_201_CREATED)
def create_meal_record(payload: MealRecordInput, db: DbSession, user: CurrentUser) -> MealRecordOut:
    record = meal_records.create_record(db, user.id, payload)
    return meal_records.to_out(record)


@router.patch("/{record_id}", response_model=MealRecordOut)
def update_meal_record(
    record_id: uuid.UUID, payload: MealRecordInput, db: DbSession, user: CurrentUser
) -> MealRecordOut:
    record = meal_records.get_owned_record(db, user.id, record_id)
    updated = meal_records.replace_items(db, record, payload)
    return meal_records.to_out(updated)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal_record(record_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Response:
    record = meal_records.get_owned_record(db, user.id, record_id)

    # 刪除紀錄時同步刪除照片檔案（OQ-5 的現行假設）。
    if record.photo_path:
        get_photo_storage().delete(record.photo_path)

    db.delete(record)
    db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{record_id}/photo")
def get_meal_photo(record_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Response:
    """經後端驗證擁有者後回傳照片。

    刻意不開放靜態目錄——路徑可猜測即可讀取不是存取控制（FR-044）。
    """
    record = meal_records.get_owned_record(db, user.id, record_id)
    if not record.photo_path:
        raise AppError("NOT_FOUND")

    storage = get_photo_storage()
    if not storage.exists(record.photo_path):
        raise AppError("NOT_FOUND")

    return Response(
        content=storage.read(record.photo_path),
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=3600"},
    )
