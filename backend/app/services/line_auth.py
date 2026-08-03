"""LINE 身分驗證。

★ 憲章原則 I — 後端驗證邏輯共用一套，不因入口不同分岔
========================================================
兩個入口的差異**只在於怎麼取得 ID Token**：

    LIFF     ──► 前端直接給 ID Token ──┐
                                        ├──► verify_line_identity() ──► LineIdentity
    一般網頁 ──► code 換 ID Token ─────┘

`verify_line_identity()` 之後的所有流程（建立／查詢 user、簽發 session、
判斷是否需引導建檔）完全共用。

`LineIdentity` 刻意**不帶來源入口欄位**——從型別上杜絕下游寫出
`if entry == "liff"` 這種分支。
"""

import logging
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import create_access_token
from app.db.models import User
from app.schemas.profile import SessionResponse, UserOut

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LineIdentity:
    """已驗證的 LINE 身分。**不含來源入口資訊**（見模組說明）。"""

    line_user_id: str
    display_name: str | None
    picture_url: str | None


async def verify_line_identity(id_token: str) -> LineIdentity:
    """★ 單一驗證核心。兩個入口都必須經過此函式。"""
    settings = get_settings()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                settings.line_verify_endpoint,
                data={"id_token": id_token, "client_id": settings.line_channel_id},
            )
    except httpx.HTTPError as exc:
        logger.warning("LINE ID Token 驗證請求失敗：%s", exc)
        raise AppError("UNAUTHORIZED") from exc

    if response.status_code != 200:
        logger.info("LINE ID Token 驗證未通過：%s", response.text)
        raise AppError("UNAUTHORIZED")

    payload = response.json()
    sub = payload.get("sub")
    if not sub:
        raise AppError("UNAUTHORIZED")

    return LineIdentity(
        line_user_id=str(sub),
        display_name=payload.get("name"),
        picture_url=payload.get("picture"),
    )


async def exchange_code_for_id_token(code: str, redirect_uri: str) -> str:
    """一般網頁 OAuth：以 authorization code 換取 ID Token。

    這是網頁入口**唯一**多出來的步驟；換到 ID Token 之後即交回
    verify_line_identity() 走與 LIFF 完全相同的路徑。
    """
    settings = get_settings()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                settings.line_token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": settings.line_channel_id,
                    "client_secret": settings.line_channel_secret,
                },
            )
    except httpx.HTTPError as exc:
        logger.warning("LINE token 交換失敗：%s", exc)
        raise AppError("UNAUTHORIZED") from exc

    if response.status_code != 200:
        logger.info("LINE token 交換被拒：%s", response.text)
        raise AppError("UNAUTHORIZED")

    id_token = response.json().get("id_token")
    if not id_token:
        raise AppError("UNAUTHORIZED")
    return str(id_token)


def upsert_user(db: Session, identity: LineIdentity) -> User:
    """依 line_user_id 建立或更新使用者。

    同一 LINE 身分不論從哪個入口登入都對應同一列——這是 FR-007
    「兩入口看到同一份資料」在資料層的保證。
    """
    user = db.scalar(select(User).where(User.line_user_id == identity.line_user_id))

    if user is None:
        user = User(line_user_id=identity.line_user_id)
        db.add(user)

    # 每次登入更新顯示資訊，讓使用者改了 LINE 暱稱後能反映。
    user.display_name = identity.display_name
    user.picture_url = identity.picture_url

    db.flush()
    db.refresh(user)
    return user


def issue_session(user: User) -> SessionResponse:
    """簽發本站 session。兩個入口共用。"""
    token, expires_in = create_access_token(user.id)
    return SessionResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
        # 尚未建檔時前端須導向 onboarding（FR-013）。
        profile_completed=user.health_profile is not None,
    )


async def login_with_id_token(db: Session, id_token: str) -> SessionResponse:
    """★ 兩個入口最終都收斂到這裡。"""
    identity = await verify_line_identity(id_token)
    user = upsert_user(db, identity)
    return issue_session(user)
