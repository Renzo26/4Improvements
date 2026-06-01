from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# Supabase exige SSL — asyncpg recebe a flag via connect_args.
# Conexão pelo Session Pooler (porta 5432): compatível com IPv4 (VPS/EasyPanel)
# e em modo sessão, o que preserva prepared statements (sem precisar
# desativar o statement cache, como seria exigido pelo Transaction Pooler).
engine = create_async_engine(
    settings.database_url,
    connect_args={"ssl": "require"},
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=settings.app_env == "development",
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
