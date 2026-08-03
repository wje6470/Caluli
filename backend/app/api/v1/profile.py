"""使用者與個人健康檔案端點。"""

from fastapi import APIRouter

from app.core.clock import now_utc
from app.core.deps import CurrentUser, DbSession
from app.db.models import HealthProfile
from app.schemas.profile import (
    HealthProfileInput,
    HealthProfileOut,
    MeResponse,
    UserOut,
)
from app.services.targets import calculate_targets

router = APIRouter(tags=["profile"])


@router.get("/me", response_model=MeResponse)
def get_me(user: CurrentUser) -> MeResponse:
    profile = user.health_profile
    return MeResponse(
        user=UserOut.model_validate(user),
        # 前端據此決定是否導向 onboarding（FR-013）。
        profile_completed=profile is not None,
        profile=HealthProfileOut.model_validate(profile) if profile else None,
    )


@router.put("/me/profile", response_model=HealthProfileOut)
def upsert_profile(
    payload: HealthProfileInput, db: DbSession, user: CurrentUser
) -> HealthProfileOut:
    """建立或更新個人健康檔案，並重算每日目標。

    ⚠️ 重算**不觸碰任何 meal_items**（FR-016）——歷史紀錄的營養值為
    寫入當下的快照，不會因目標變動而改變。
    """
    targets = calculate_targets(
        gender=payload.gender,
        age_years=payload.age_years,
        height_cm=payload.height_cm,
        weight_kg=payload.weight_kg,
        activity_level=payload.activity_level,
    )

    profile = user.health_profile
    if profile is None:
        profile = HealthProfile(user_id=user.id)
        db.add(profile)

    profile.gender = payload.gender
    profile.age_years = payload.age_years
    profile.height_cm = payload.height_cm
    profile.weight_kg = payload.weight_kg
    profile.activity_level = payload.activity_level

    # 目標值一律由後端計算——請求中若帶這些欄位也不會被採用。
    profile.bmr_kcal = targets.bmr_kcal
    profile.tdee_kcal = targets.tdee_kcal
    profile.target_protein_g = targets.protein_g
    profile.target_carbs_g = targets.carbs_g
    profile.target_fat_g = targets.fat_g
    profile.computed_at = now_utc()

    db.flush()
    db.refresh(profile)
    return HealthProfileOut.model_validate(profile)
