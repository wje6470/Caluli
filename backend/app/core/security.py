"""本站 session token 的簽發與解析（research.md R-04）。

刻意不使用 LINE 的 access token 作為本站憑證：Bearer token 是唯一在
LIFF WebView、一般瀏覽器與未來 Flutter 原生端三種環境行為一致的方案
（憲章原則 III）。
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    """回傳 (token, expires_in_seconds)。"""
    settings = get_settings()
    expires_in = settings.jwt_expires_seconds
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str) -> uuid.UUID | None:
    """解析 token，失敗一律回 None（呼叫端轉為 401）。"""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None

    sub = payload.get("sub")
    if not sub:
        return None
    try:
        return uuid.UUID(sub)
    except ValueError:
        return None
