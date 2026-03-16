from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from core.database import Base
import models  # noqa: F401

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _normalize_database_url(url: str | None) -> str | None:
    if not url:
        return url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        if "sslmode" not in url:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}sslmode=require"
    return url


database_url = _normalize_database_url(os.getenv("DATABASE_URL"))
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
