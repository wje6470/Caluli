"""資料庫 engine 與 session。

連線策略依部署形態而異——這是 serverless 與長時運行伺服器最大的差別：

  長時運行（uvicorn）  自帶連線池，走 Supabase 的 **session pooler（5432）**
  Serverless（Vercel） 每次呼叫都是短生命週期，自帶連線池反而會耗盡
                       資料庫連線數。應走 **transaction pooler（6543）**、
                       關閉 SQLAlchemy 的池化（NullPool），並停用
                       prepared statements（pgbouncer transaction 模式不支援，
                       psycopg3 預設會使用而報錯）。
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_settings = get_settings()

#: 走 pgbouncer 的 transaction 模式時，psycopg 必須停用 prepared statements。
_uses_transaction_pooler = ":6543" in _settings.database_url or _settings.serverless

_connect_args: dict[str, object] = {}
if _uses_transaction_pooler:
    # prepare_threshold=None 代表「永不使用 prepared statements」。
    _connect_args["prepare_threshold"] = None

engine = create_engine(
    _settings.database_url,
    # Serverless 下不做連線池：函式實例短命且數量不可預期，
    # 池化只會累積閒置連線並打爆資料庫的連線上限。
    poolclass=NullPool if _settings.serverless else None,
    pool_pre_ping=not _settings.serverless,
    connect_args=_connect_args,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Iterator[Session]:
    """FastAPI 依賴：每個請求一個 session。"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
