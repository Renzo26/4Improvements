"""Configuração e fixtures dos testes de integração.

Os testes exercitam o app FastAPI real (via httpx ASGITransport) contra a base
de dados apontada por `DATABASE_URL`. Cada teste usa dados únicos para não
colidir entre execuções.
"""

import asyncio
import uuid

from dotenv import load_dotenv

load_dotenv()

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from main import app


@pytest.fixture(scope="session")
def event_loop():
    """Um único event loop para toda a sessão.

    Necessário porque o engine async (asyncpg) é global e o seu pool fica ligado
    ao loop ativo na primeira utilização; um loop por teste causaria erros de
    "Future attached to a different loop".
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def unique_email() -> str:
    return f"test_{uuid.uuid4().hex[:12]}@example.com"


def unique_phone() -> str:
    # +351 9 + 8 dígitos pseudo-únicos
    return "+3519" + uuid.uuid4().int.__str__()[:8]


async def create_lead(client: httpx.AsyncClient, **overrides) -> dict:
    """Cria uma lead válida e devolve o corpo da resposta (201)."""
    payload = {
        "name": "Mariana Silva",
        "email": unique_email(),
        "phone": unique_phone(),
        "source": "meta_ads",
        "message": "Pretendo comprar apartamento em Lisboa.",
    }
    payload.update(overrides)
    resp = await client.post("/contacts/leads", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def backdate_lead(lead_id: str, minutes: int) -> None:
    """Recua o `created_at` da lead N minutos, para testar o SLA sem esperar."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                "UPDATE leads SET created_at = now() - make_interval(mins => :m) "
                "WHERE id = :id"
            ),
            {"m": minutes, "id": lead_id},
        )
        await session.commit()
