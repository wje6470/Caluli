"""一次辨識請求的生命週期紀錄。

這是**同步／非同步遷移的接縫**（research.md R-07）。本輪同步實作下
`processing` 只短暫存在於請求處理期間，但欄位先備齊，遷移時
不需要 schema 變更。
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, uuid_pk

STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

ERROR_TIMEOUT = "TIMEOUT"
ERROR_UNAVAILABLE = "UNAVAILABLE"
ERROR_BAD_RESPONSE = "BAD_RESPONSE"


class RecognitionJob(Base):
    __tablename__ = "recognition_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('processing', 'completed', 'failed')",
            name="ck_recognition_jobs_status",
        ),
        Index("ix_recognition_jobs_user_requested", "user_id", "requested_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=STATUS_PROCESSING)

    #: 重試時重用，使用者不需重新上傳（FR-028）。
    photo_path: Mapped[str] = mapped_column(String(512), nullable=False)

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: 供 OQ-1／OQ-4 的實測依據。
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    #: 0 代表未偵測到食物——這仍是 **completed**，不是 failed（FR-027）。
    item_count: Mapped[int | None] = mapped_column(SmallInteger)
    #: 辨識服務回傳的 message，原樣保留供前端顯示。
    service_message: Mapped[str | None] = mapped_column(Text)

    error_code: Mapped[str | None] = mapped_column(String(32))
    retry_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    @property
    def no_food_detected(self) -> bool:
        """未偵測到食物：成功完成但品項數為 0。"""
        return self.status == STATUS_COMPLETED and (self.item_count or 0) == 0
