from alembic import context
from finboy.core.config import Settings
from finboy.core.logging import configure_logging
from finboy.db import models as models
from finboy.db.base import Base
from sqlalchemy import create_engine, pool

# Keep every model imported so Alembic sees the complete schema.
settings = Settings()
configure_logging(settings.log_level)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(
        settings.database_url.get_secret_value(),
        poolclass=pool.NullPool,
        hide_parameters=True,
        connect_args={"connect_timeout": 3},
    )
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
