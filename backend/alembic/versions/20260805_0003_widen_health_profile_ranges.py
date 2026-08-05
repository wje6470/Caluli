"""放寬 health_profiles 年齡／身高／體重 CHECK 範圍

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-05

年齡 15–90 → 1–100，身高 100–250 → 60–280，體重 25–300 → 30–120。
與 Pydantic HealthProfileInput（backend/app/schemas/profile.py）雙層驗證
同步調整，僅替換既有 CHECK CONSTRAINT，不變更欄位型別。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINTS = {
    "ck_health_profiles_age": ("age_years BETWEEN 15 AND 90", "age_years BETWEEN 1 AND 100"),
    "ck_health_profiles_height": (
        "height_cm BETWEEN 100 AND 250",
        "height_cm BETWEEN 60 AND 280",
    ),
    "ck_health_profiles_weight": (
        "weight_kg BETWEEN 25 AND 300",
        "weight_kg BETWEEN 30 AND 120",
    ),
}


def upgrade() -> None:
    for name, (_old, new) in _CONSTRAINTS.items():
        op.drop_constraint(name, "health_profiles", type_="check")
        op.create_check_constraint(name, "health_profiles", new)


def downgrade() -> None:
    for name, (old, _new) in _CONSTRAINTS.items():
        op.drop_constraint(name, "health_profiles", type_="check")
        op.create_check_constraint(name, "health_profiles", old)
