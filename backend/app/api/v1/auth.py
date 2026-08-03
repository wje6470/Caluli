"""登入端點。

兩支端點看似分開，但**驗證邏輯完全共用**（憲章原則 I）：
每支端點只負責「取得可驗證的 ID Token」，之後一律交給
line_auth.login_with_id_token()。端點內不得出現任何依入口分岔的
業務邏輯。
"""

from fastapi import APIRouter

from app.core.deps import DbSession
from app.schemas.profile import LiffLoginRequest, SessionResponse, WebCallbackRequest
from app.services import line_auth

router = APIRouter(prefix="/auth/line", tags=["auth"])


@router.post("/liff", response_model=SessionResponse)
async def login_via_liff(payload: LiffLoginRequest, db: DbSession) -> SessionResponse:
    """LIFF 入口：前端已於 LINE 內取得 ID Token。"""
    return await line_auth.login_with_id_token(db, payload.id_token)


@router.post("/callback", response_model=SessionResponse)
async def login_via_web_oauth(payload: WebCallbackRequest, db: DbSession) -> SessionResponse:
    """一般網頁入口：多一次 code → ID Token 的交換，其餘完全相同。"""
    id_token = await line_auth.exchange_code_for_id_token(payload.code, payload.redirect_uri)
    return await line_auth.login_with_id_token(db, id_token)
