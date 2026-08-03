"""通用食物營養對照表查詢。

憲章原則 V：本端點**僅**查詢通用食物對照表。店家／餐點資料屬第二輪，
將有各自獨立的端點與資料表，不與此處共用。
"""

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.recognition import FoodReferenceOut, FoodSearchResponse, Per100g
from app.services import recognition_client

router = APIRouter(prefix="/foods", tags=["foods"])


@router.get("/search", response_model=FoodSearchResponse)
def search_foods(
    db: DbSession,
    user: CurrentUser,  # noqa: ARG001 — 僅用於要求登入
    q: str = Query(min_length=1),
    limit: int = Query(default=20, le=50),
) -> FoodSearchResponse:
    """供辨識結果確認畫面的「手動修正食物名稱」使用（FR-037）。"""
    rows = recognition_client.search_foods(db, q, limit)
    return FoodSearchResponse(
        foods=[
            FoodReferenceOut(
                id=row.id,
                name=row.name,
                default_portion_grams=row.default_portion_grams,
                per_100g=Per100g(
                    calories_kcal=row.calories_kcal_per_100g,
                    protein_g=row.protein_g_per_100g,
                    carbs_g=row.carbs_g_per_100g,
                    fat_g=row.fat_g_per_100g,
                ),
            )
            for row in rows
        ]
    )
