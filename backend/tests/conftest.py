"""共用測試設定。

整合測試以 testcontainers 跑真 PostgreSQL——本設計依賴 TIMESTAMPTZ、
NUMERIC 精度與 ON DELETE SET NULL 的實際行為，SQLite 的差異會讓問題
拖到上線才暴露（research.md R-15）。

Docker 不可用時整合測試自動 skip，讓不依賴 DB 的單元／契約測試仍可跑。
"""

import contextlib
import os
import sys
import warnings
from pathlib import Path

import pytest

# 讓測試能匯入辨識 stub 服務（契約測試需要驗證 stub 本身符合契約文件）。
STUB_DIR = Path(__file__).resolve().parents[2] / "tools" / "recognition-stub"
if str(STUB_DIR) not in sys.path:
    sys.path.insert(0, str(STUB_DIR))


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """提供測試用 PostgreSQL 連線。

    解析順序：
      1. TEST_DATABASE_URL 環境變數 —— 指向既有的 PostgreSQL 實例
         （CI 的 service container、或本機直接跑的 postgres）
      2. testcontainers 起一次性容器 —— 需要 Docker
      3. 兩者皆不可用 → skip（讓不依賴 DB 的測試仍可跑）
    """
    existing = os.getenv("TEST_DATABASE_URL")
    if existing:
        yield existing
        return

    # testcontainers 於匯入時發出 DeprecationWarning，而該警告會被歸因於
    # 本檔案（stacklevel 之故），pyproject 的模組過濾器攔不到。就地抑制，
    # 避免第三方套件的 deprecation 讓整合測試在 skip 之前就 error。
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        try:
            from testcontainers.postgres import PostgresContainer
        except ImportError:  # pragma: no cover
            pytest.skip("未安裝 testcontainers，且未設定 TEST_DATABASE_URL")

    try:
        container = PostgresContainer("postgres:16-alpine", driver="psycopg")
        container.start()
    except Exception as exc:  # pragma: no cover - 依賴本機 Docker 是否運行
        pytest.skip(f"Docker 不可用，跳過整合測試：{exc}")

    try:
        yield container.get_connection_url()
    finally:
        container.stop()


@pytest.fixture(scope="session")
def db_engine(postgres_url: str):
    from sqlalchemy import create_engine, text

    from app.db.models import Base

    engine = create_engine(postgres_url, future=True)
    # 與 migration 同樣採 best-effort：託管服務上可能無 CREATE EXTENSION 權限，
    # 而 gen_random_uuid() 自 PostgreSQL 13 起已是核心函式。
    with contextlib.suppress(Exception), engine.begin() as conn:
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """每個測試一個交易，結束後 rollback，測試之間互不污染。"""
    from sqlalchemy.orm import Session

    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
