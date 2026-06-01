"""Lista as tabelas e colunas criadas no schema public (verificação pós-migration).

Uso:
    python -m scripts.check_schema
"""

import asyncio

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import text

from app.core.database import engine

TABLES = ("contacts", "leads", "interactions", "lead_history")


async def main() -> None:
    async with engine.connect() as conn:
        for table in TABLES:
            result = await conn.execute(
                text(
                    "select column_name, data_type "
                    "from information_schema.columns "
                    "where table_schema = 'public' and table_name = :t "
                    "order by ordinal_position"
                ),
                {"t": table},
            )
            rows = result.fetchall()
            print(f"\n== {table} ({len(rows)} colunas) ==")
            for name, dtype in rows:
                print(f"  - {name}: {dtype}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
