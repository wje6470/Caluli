"""Alembic 環境設定。DATABASE_URL 由應用設定提供，不重複定義於 alembic.ini。"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.db.models import Base  # 匯入所有 model 供 autogenerate 掃描

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ⚠️ set_main_option 的值會經過 ConfigParser 的字串插值，其中 % 具特殊意義。
# URL-encoded 的密碼（例如 @ → %40）會被當成插值語法而拋
# "invalid interpolation syntax"，因此必須把 % 逸出為 %%。
# 注意這只影響 Alembic；應用本身用 create_engine 直接吃原始 URL，不需處理。
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
