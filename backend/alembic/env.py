import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

from app.core.config import get_settings
from app.core.database import Base
import app.models  # noqa: F401  — registra os models no Base.metadata

# Objeto de configuração do Alembic (lê o alembic.ini)
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata-alvo para o autogenerate
target_metadata = Base.metadata

# A URL vem das settings (.env), não do alembic.ini — segredo fora do código.
settings = get_settings()
DATABASE_URL = settings.database_url


def run_migrations_offline() -> None:
    """Gera SQL sem conectar (modo offline)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Conecta ao Supabase (Session Pooler + SSL) e aplica as migrations."""
    connectable = create_async_engine(
        DATABASE_URL,
        connect_args={"ssl": "require"},
        pool_pre_ping=True,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
