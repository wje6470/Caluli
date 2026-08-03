"""通用食物營養對照表（拍照辨識用）。

⚠️ 憲章原則 V — 資料表分離
====================================
此表是「拍照辨識用之通用食物營養對照表」。第二輪「推薦餐廳」模組的
「特定店家／餐點營養值」將是**另一組完全獨立的資料表**。

兩者之間**禁止**：
  * 建立任何方向的外鍵
  * 合併為同一張表
  * 以 type / category 欄位混存於單表

理由：通用對照表是辨識模型的估算基準，店家餐點營養值是商家提供的既定
數值，正確性責任歸屬不同，混存會使錯誤資料互相汙染且無法回溯來源。
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, uuid_pk


class FoodNutritionReference(Base, TimestampMixin):
    __tablename__ = "food_nutrition_references"
    __table_args__ = (
        CheckConstraint("calories_kcal_per_100g >= 0", name="ck_food_ref_calories"),
        CheckConstraint("protein_g_per_100g >= 0", name="ck_food_ref_protein"),
        CheckConstraint("carbs_g_per_100g >= 0", name="ck_food_ref_carbs"),
        CheckConstraint("fat_g_per_100g >= 0", name="ck_food_ref_fat"),
        CheckConstraint("default_portion_grams > 0", name="ck_food_ref_default_portion"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    #: 對應 HF 分類模型輸出的類別標籤，是辨識結果查表的鍵。
    model_label: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    #: 供搜尋比對用（GET /foods/search）。
    name_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    calories_kcal_per_100g: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    protein_g_per_100g: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    carbs_g_per_100g: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    fat_g_per_100g: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    #: 系統設定的預設份量（FR-022）。**非模型輸出**——HF 分類模型無法
    #: 估算克數，這是本產品改採「預設值 + 使用者調整」流程的根本原因。
    default_portion_grams: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)

    #: 停用項目不再出現於新辨識結果；既有紀錄因採快照而不受影響。
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    source: Mapped[str | None] = mapped_column(String(255))


def normalize_food_name(name: str) -> str:
    """搜尋用正規化：去除空白、統一小寫。"""
    return "".join(name.split()).lower()
