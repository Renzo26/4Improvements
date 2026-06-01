"""Teste de fumaça do ciclo de vida completo de uma lead.

Exercita: criação → primeiro contacto (SLA) → qualificação (roteamento) →
histórico → listagem, usando o app FastAPI real contra o Supabase.

Uso:
    python -m scripts.smoke_lifecycle
"""

import asyncio
import json
import time

from dotenv import load_dotenv

load_dotenv()

import httpx

from main import app


async def main() -> None:
    email = f"lifecycle+{int(time.time())}@email.com"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1) Criar lead
        r1 = await client.post(
            "/contacts/leads",
            json={
                "name": "Carlos Pereira",
                "email": email,
                "source": "site",
                "message": "Quero vender o meu apartamento no Porto.",
            },
        )
        assert r1.status_code == 201, r1.text
        lead_id = r1.json()["lead"]["id"]
        print("== Lead criada ==", lead_id)

        # 2) Primeiro contacto → SLA (criado agora, deve ser dentro_sla)
        r2 = await client.post(
            f"/leads/{lead_id}/first-contact",
            json={"type": "chamada", "note": "Liguei e apresentei a empresa."},
        )
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        print("== 1.º contacto ==", body2["status"], "| sla:", body2["sla_status"])
        assert body2["status"] == "contactada"
        assert body2["sla_status"] == "dentro_sla"

        # 2b) Repetir 1.º contacto deve dar 409
        r2b = await client.post(
            f"/leads/{lead_id}/first-contact",
            json={"type": "email"},
        )
        assert r2b.status_code == 409, r2b.text
        print("== 1.º contacto repetido (esperado 409) ==", r2b.status_code)

        # 3) Qualificação → roteamento (vender_imovel → sell_advisor_mediacao)
        r3 = await client.post(
            f"/leads/{lead_id}/qualification",
            json={"interest": "vender_imovel"},
        )
        assert r3.status_code == 200, r3.text
        body3 = r3.json()
        print("== Qualificação ==", body3["status"], "| área:", body3["responsible_area"])
        assert body3["status"] == "encaminhada"
        assert body3["interest"] == "vender_imovel"
        assert body3["responsible_area"] == "sell_advisor_mediacao"

        # 4) Histórico
        r4 = await client.get(f"/leads/{lead_id}/history")
        assert r4.status_code == 200, r4.text
        actions = [h["action_type"] for h in r4.json()]
        print("== Histórico ==", actions)
        assert actions == [
            "lead_criada",
            "primeiro_contacto",
            "qualificacao",
            "encaminhamento",
        ]

        # 5) GET por id + listagem com filtro
        r5 = await client.get(f"/leads/{lead_id}")
        assert r5.status_code == 200, r5.text

        r6 = await client.get("/leads", params={"status": "encaminhada", "limit": 5})
        assert r6.status_code == 200, r6.text
        assert any(item["id"] == lead_id for item in r6.json())

        # 6) 404 em lead inexistente
        r7 = await client.get("/leads/00000000-0000-0000-0000-000000000000")
        assert r7.status_code == 404, r7.text

        print("\n[OK] Ciclo de vida completo passou.")
        print(json.dumps(body3, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
