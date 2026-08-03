"""使用者。以 LINE 身分識別（憲章原則 I）。"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.db.models.health_profile import HealthProfile

ROLE_USER = "user"
ROLE_ADMIN = "admin"


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),)

    id: Mapped[uuid.UUID] = uuid_pk()

    #: LINE ID Token 的 sub。不論來自 LIFF 或網頁 OAuth 皆寫入同一欄位——
    #: 這是「後端驗證邏輯不因入口分岔」在資料層的體現（憲章原則 I）。
    line_user_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    picture_url: Mapped[str | None] = mapped_column(String(1024))

    #: 憲章原則 IV 的權限層預留。本輪一律為 'user'，且**不提供任何**
    #: 將其改為 'admin' 的 API；需指派管理員時於資料庫直接操作。
    #: 先放此欄位可讓第二輪加入後台時免除資料遷移與端點改寫。
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ROLE_USER, server_default=ROLE_USER
    )

    health_profile: Mapped["HealthProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


__all__ = ["User", "ROLE_USER", "ROLE_ADMIN", "PgUUID"]
