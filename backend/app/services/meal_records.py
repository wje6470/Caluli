"""飲食紀錄的組裝與驗算。"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import now_utc, to_record_date
from app.core.errors import AppError
from app.db.models import MealItem, MealRecord, RecognitionJob
from app.schemas.meal_record import (
    MealItemInput,
    MealItemOut,
    MealRecordInput,
    MealRecordOut,
)
from app.schemas.meal_record import (
    Nutrients as NutrientsSchema,
)
from app.schemas.recognition import Per100g
from app.services import nutrition


def _to_domain(per_100g: Per100g) -> nutrition.Nutrients:
    return nutrition.Nutrients(
        calories_kcal=per_100g.calories_kcal,
        protein_g=per_100g.protein_g,
        carbs_g=per_100g.carbs_g,
        fat_g=per_100g.fat_g,
    )


def _build_item(payload: MealItemInput, order: int) -> MealItem:
    """建立品項，並以後端公式重新驗算營養值。

    客戶端送來的換算結果不被採信（research.md R-09）——這裡直接以
    per_100g × portion_grams / 100 重算，防止竄改污染趨勢統計。
    """
    per_100g = _to_domain(payload.per_100g)
    computed = nutrition.scale(per_100g, payload.portion_grams)

    return MealItem(
        food_reference_id=payload.food_reference_id,
        display_order=order,
        food_name=payload.food_name,
        default_portion_grams=payload.default_portion_grams,
        portion_grams=payload.portion_grams,
        calories_kcal_per_100g=per_100g.calories_kcal,
        protein_g_per_100g=per_100g.protein_g,
        carbs_g_per_100g=per_100g.carbs_g,
        fat_g_per_100g=per_100g.fat_g,
        calories_kcal=computed.calories_kcal,
        protein_g=computed.protein_g,
        carbs_g=computed.carbs_g,
        fat_g=computed.fat_g,
        recognition_confidence=payload.recognition_confidence,
        is_user_modified=payload.is_user_modified,
    )


def create_record(db: Session, user_id: uuid.UUID, payload: MealRecordInput) -> MealRecord:
    captured_at = payload.captured_at or now_utc()

    photo_path: str | None = None
    if payload.recognition_id:
        job = db.get(RecognitionJob, payload.recognition_id)
        if job and job.user_id == user_id:
            photo_path = job.photo_path

    record = MealRecord(
        user_id=user_id,
        # 歸屬日期物化，不在查詢時換算（FR-040）。
        record_date=to_record_date(captured_at),
        meal_type=payload.meal_type,
        captured_at=captured_at,
        photo_path=photo_path,
        recognition_job_id=payload.recognition_id,
    )
    record.items = [_build_item(item, index) for index, item in enumerate(payload.items)]

    db.add(record)
    db.flush()
    db.refresh(record)
    return record


def replace_items(db: Session, record: MealRecord, payload: MealRecordInput) -> MealRecord:
    """以新內容取代既有品項（編輯紀錄，FR-042）。"""
    record.meal_type = payload.meal_type
    if payload.captured_at:
        record.captured_at = payload.captured_at
        record.record_date = to_record_date(payload.captured_at)

    record.items.clear()
    db.flush()
    record.items = [_build_item(item, index) for index, item in enumerate(payload.items)]

    db.add(record)
    db.flush()
    db.refresh(record)
    return record


def get_owned_record(db: Session, user_id: uuid.UUID, record_id: uuid.UUID) -> MealRecord:
    record = db.get(MealRecord, record_id)
    # 非本人一律 404，不回 403——避免洩漏資源是否存在（FR-044）。
    if record is None or record.user_id != user_id:
        raise AppError("NOT_FOUND")
    return record


def list_records(db: Session, user_id: uuid.UUID, on_date) -> list[MealRecord]:
    stmt = (
        select(MealRecord)
        .where(MealRecord.user_id == user_id, MealRecord.record_date == on_date)
        .order_by(MealRecord.captured_at)
    )
    return list(db.scalars(stmt).all())


def totals_of(record: MealRecord) -> nutrition.Nutrients:
    return nutrition.sum_all(
        [
            nutrition.Nutrients(
                calories_kcal=item.calories_kcal,
                protein_g=item.protein_g,
                carbs_g=item.carbs_g,
                fat_g=item.fat_g,
            )
            for item in record.items
        ]
    )


def to_out(record: MealRecord) -> MealRecordOut:
    totals = totals_of(record)
    return MealRecordOut(
        id=record.id,
        record_date=record.record_date,
        meal_type=record.meal_type,
        captured_at=record.captured_at,
        has_photo=bool(record.photo_path),
        items=[
            MealItemOut(
                id=item.id,
                food_reference_id=item.food_reference_id,
                food_name=item.food_name,
                portion_grams=item.portion_grams,
                default_portion_grams=item.default_portion_grams,
                per_100g=Per100g(
                    calories_kcal=item.calories_kcal_per_100g,
                    protein_g=item.protein_g_per_100g,
                    carbs_g=item.carbs_g_per_100g,
                    fat_g=item.fat_g_per_100g,
                ),
                recognition_confidence=(
                    float(item.recognition_confidence)
                    if item.recognition_confidence is not None
                    else None
                ),
                is_user_modified=item.is_user_modified,
                nutrients=NutrientsSchema(
                    calories_kcal=item.calories_kcal,
                    protein_g=item.protein_g,
                    carbs_g=item.carbs_g,
                    fat_g=item.fat_g,
                ),
            )
            for item in record.items
        ],
        totals=NutrientsSchema(
            calories_kcal=totals.calories_kcal,
            protein_g=totals.protein_g,
            carbs_g=totals.carbs_g,
            fat_g=totals.fat_g,
        ),
    )


def utc_now() -> datetime:
    return now_utc()
