"""管理端 schemas（對應 specs/003-admin-backoffice/contracts/admin-api.yaml）。

店家與餐點的 schema 於 US2／US3 加入本檔。目前僅含身分確認所需的最小結構。
"""

import uuid
from typing import Literal

from pydantic import BaseModel


class AdminSessionOut(BaseModel):
    """管理員身分確認的回應。

    刻意只有三個欄位——前端守衛只需要知道「你是管理員」。不放 LINE
    憑證、不放管理員名單、不放權限細目，避免擴大暴露面。
    """

    user_id: uuid.UUID
    display_name: str | None = None
    #: 非管理員到不了這支端點，故型別上就只可能是 admin。
    role: Literal["admin"]
