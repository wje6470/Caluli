"""使用者與個人健康檔案 schemas。"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Gender = Literal["male", "female"]
ActivityLevel = Literal["low", "moderate", "high"]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str | None = None
    picture_url: str | None = None


class HealthProfileInput(BaseModel):
    """個人資訊輸入。

    範圍限制即 FR-014 的合理生理範圍，與資料表 CHECK 一致（雙層驗證：
    此層負責產生可讀的錯誤訊息，DB 層負責兜底）。

    ⚠️ 刻意**不含** bmr_kcal / tdee_kcal / target_* 欄位——那些一律由
    後端計算，客戶端即使送來也不會被採用（單一真實來源）。
    """

    gender: Gender
    age_years: int = Field(ge=1, le=100)
    height_cm: Decimal = Field(ge=60, le=280)
    weight_kg: Decimal = Field(ge=30, le=120)
    activity_level: ActivityLevel


class HealthProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    gender: str
    age_years: int
    height_cm: Decimal
    weight_kg: Decimal
    activity_level: str

    bmr_kcal: Decimal
    #: 即每日建議熱量。
    tdee_kcal: Decimal
    target_protein_g: Decimal
    target_carbs_g: Decimal
    target_fat_g: Decimal
    computed_at: datetime


class MeResponse(BaseModel):
    user: UserOut
    #: false 時前端必須導向個人資訊填寫流程（FR-013）。
    profile_completed: bool
    profile: HealthProfileOut | None = None


class SessionResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    user: UserOut
    profile_completed: bool


class LiffLoginRequest(BaseModel):
    id_token: str


class WebCallbackRequest(BaseModel):
    code: str
    redirect_uri: str
    state: str
