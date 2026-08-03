"""initial schema — 6 tables for round 1 MVP

Revision ID: 0001
Revises:
Create Date: 2026-08-03

================================================================================
憲章原則 V 稽核紀錄（tasks.md T017）
================================================================================
檢查日期：2026-08-03

1. 本 migration 建立的資料表共 6 張：
     users, health_profiles, food_nutrition_references,
     meal_records, meal_items, recognition_jobs
   其中**沒有任何**店家（merchant/store/shop）或餐點（menu_item）資料表。
   第二輪「推薦餐廳」模組的店家／餐點資料表不屬本輪範圍。

2. food_nutrition_references 的外鍵檢查：
     - 出向外鍵：無（此表不指向任何其他表）
     - 入向外鍵：僅 meal_items.food_reference_id（ON DELETE SET NULL）
   meal_items 是本輪自己的飲食紀錄品項表，屬「通用食物對照表」體系內部
   的來源追溯，不是店家餐點資料。憲章禁止的是「通用食物對照表 ↔ 店家
   餐點表」之間的關聯，本 migration 未建立任何此類關聯。

3. 未使用 type / category 欄位於單表內混存兩類營養資料。

結論：符合憲章原則 V（資料表分離）。
================================================================================
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("line_user_id", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("picture_url", sa.String(1024), nullable=True),
        sa.Column("role", sa.String(16), server_default="user", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_line_user_id", "users", ["line_user_id"], unique=True)

    op.create_table(
        "health_profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gender", sa.String(8), nullable=False),
        sa.Column("age_years", sa.SmallInteger(), nullable=False),
        sa.Column("height_cm", sa.Numeric(5, 1), nullable=False),
        sa.Column("weight_kg", sa.Numeric(5, 1), nullable=False),
        sa.Column("activity_level", sa.String(16), nullable=False),
        sa.Column("bmr_kcal", sa.Numeric(7, 2), nullable=False),
        sa.Column("tdee_kcal", sa.Numeric(7, 2), nullable=False),
        sa.Column("target_protein_g", sa.Numeric(6, 1), nullable=False),
        sa.Column("target_carbs_g", sa.Numeric(6, 1), nullable=False),
        sa.Column("target_fat_g", sa.Numeric(6, 1), nullable=False),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("gender IN ('male', 'female')", name="ck_health_profiles_gender"),
        sa.CheckConstraint(
            "activity_level IN ('low', 'moderate', 'high')",
            name="ck_health_profiles_activity_level",
        ),
        sa.CheckConstraint("age_years BETWEEN 15 AND 90", name="ck_health_profiles_age"),
        sa.CheckConstraint("height_cm BETWEEN 100 AND 250", name="ck_health_profiles_height"),
        sa.CheckConstraint("weight_kg BETWEEN 25 AND 300", name="ck_health_profiles_weight"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_health_profiles_user_id"),
    )

    # ⚠️ 獨立資料集。無出向外鍵，且未來的店家／餐點資料表不得與其關聯。
    op.create_table(
        "food_nutrition_references",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("model_label", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("name_normalized", sa.String(255), nullable=False),
        sa.Column("calories_kcal_per_100g", sa.Numeric(7, 2), nullable=False),
        sa.Column("protein_g_per_100g", sa.Numeric(6, 2), nullable=False),
        sa.Column("carbs_g_per_100g", sa.Numeric(6, 2), nullable=False),
        sa.Column("fat_g_per_100g", sa.Numeric(6, 2), nullable=False),
        sa.Column("default_portion_grams", sa.Numeric(6, 1), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("source", sa.String(255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("calories_kcal_per_100g >= 0", name="ck_food_ref_calories"),
        sa.CheckConstraint("protein_g_per_100g >= 0", name="ck_food_ref_protein"),
        sa.CheckConstraint("carbs_g_per_100g >= 0", name="ck_food_ref_carbs"),
        sa.CheckConstraint("fat_g_per_100g >= 0", name="ck_food_ref_fat"),
        sa.CheckConstraint("default_portion_grams > 0", name="ck_food_ref_default_portion"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_food_nutrition_references_model_label",
        "food_nutrition_references",
        ["model_label"],
        unique=True,
    )
    op.create_index(
        "ix_food_nutrition_references_name_normalized",
        "food_nutrition_references",
        ["name_normalized"],
    )

    op.create_table(
        "meal_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_date", sa.Date(), nullable=False),
        sa.Column("meal_type", sa.String(16), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("photo_path", sa.String(512), nullable=True),
        # 刻意不設外鍵：刪除 recognition_job 不應牽動已儲存的紀錄。
        sa.Column("recognition_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')",
            name="ck_meal_records_meal_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meal_records_user_date", "meal_records", ["user_id", "record_date"])

    op.create_table(
        "meal_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("meal_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("food_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("display_order", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("food_name", sa.String(255), nullable=False),
        sa.Column("default_portion_grams", sa.Numeric(6, 1), nullable=True),
        sa.Column("portion_grams", sa.Numeric(6, 1), nullable=False),
        sa.Column("calories_kcal_per_100g", sa.Numeric(7, 2), nullable=False),
        sa.Column("protein_g_per_100g", sa.Numeric(6, 2), nullable=False),
        sa.Column("carbs_g_per_100g", sa.Numeric(6, 2), nullable=False),
        sa.Column("fat_g_per_100g", sa.Numeric(6, 2), nullable=False),
        sa.Column("calories_kcal", sa.Numeric(8, 2), nullable=False),
        sa.Column("protein_g", sa.Numeric(7, 2), nullable=False),
        sa.Column("carbs_g", sa.Numeric(7, 2), nullable=False),
        sa.Column("fat_g", sa.Numeric(7, 2), nullable=False),
        sa.Column("recognition_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("is_user_modified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "portion_grams > 0 AND portion_grams <= 5000", name="ck_meal_items_portion"
        ),
        sa.CheckConstraint("calories_kcal_per_100g >= 0", name="ck_meal_items_cal_per_100g"),
        sa.CheckConstraint("protein_g_per_100g >= 0", name="ck_meal_items_pro_per_100g"),
        sa.CheckConstraint("carbs_g_per_100g >= 0", name="ck_meal_items_carb_per_100g"),
        sa.CheckConstraint("fat_g_per_100g >= 0", name="ck_meal_items_fat_per_100g"),
        sa.CheckConstraint("calories_kcal >= 0", name="ck_meal_items_calories"),
        sa.CheckConstraint("protein_g >= 0", name="ck_meal_items_protein"),
        sa.CheckConstraint("carbs_g >= 0", name="ck_meal_items_carbs"),
        sa.CheckConstraint("fat_g >= 0", name="ck_meal_items_fat"),
        sa.CheckConstraint(
            "recognition_confidence IS NULL "
            "OR (recognition_confidence >= 0 AND recognition_confidence <= 1)",
            name="ck_meal_items_confidence",
        ),
        sa.ForeignKeyConstraint(["meal_record_id"], ["meal_records.id"], ondelete="CASCADE"),
        # SET NULL：刪除對照項目不得刪掉使用者的歷史紀錄（營養值已快照於本表）。
        sa.ForeignKeyConstraint(
            ["food_reference_id"], ["food_nutrition_references.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meal_items_record", "meal_items", ["meal_record_id"])

    op.create_table(
        "recognition_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("photo_path", sa.String(512), nullable=False),
        sa.Column(
            "requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("item_count", sa.SmallInteger(), nullable=True),
        sa.Column("service_message", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(32), nullable=True),
        sa.Column("retry_count", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("raw_response", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('processing', 'completed', 'failed')",
            name="ck_recognition_jobs_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recognition_jobs_user_requested", "recognition_jobs", ["user_id", "requested_at"]
    )


def downgrade() -> None:
    op.drop_table("recognition_jobs")
    op.drop_table("meal_items")
    op.drop_table("meal_records")
    op.drop_table("food_nutrition_references")
    op.drop_table("health_profiles")
    op.drop_table("users")
