"""Teste rápido de conectividade com o Supabase (Session Pooler).

Uso:
    python -m scripts.check_db
"""

import asyncio

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import text

from app.core.database import engine


async def main() -> None:
    async with engine.connect() as conn:
        result = await conn.execute(text("select version();"))
        version = result.scalar()
        print("[OK] Conexao com o Supabase estabelecida.")
        print(version)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
