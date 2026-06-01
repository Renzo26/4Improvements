"""Teste de fumaça do endpoint POST /contacts/leads (Cenários 1 e 4 do desafio).

Exercita o app FastAPI real (e o Supabase) sem precisar subir o servidor.

Uso:
    python -m scripts.smoke_create_lead
"""

import asyncio
import json
import time

from dotenv import load_dotenv

load_dotenv()

import httpx

from main import app


async def main() -> None:
    # E-mail único por execução para o 1º POST sempre criar um contacto novo.
    email = f"mariana+{int(time.time())}@email.com"
    phone = f"+35191{int(time.time()) % 10_000_000:07d}"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Cenário 1 — nova lead de comprador
        r1 = await client.post(
            "/contacts/leads",
            json={
                "name": "Mariana Silva",
                "email": email,
                "phone": phone,
                "source": "meta_ads",
                "campaign": "compradores_lisboa",
                "message": "Pretendo comprar apartamento em Lisboa.",
            },
        )
        print("== Cenário 1: nova lead ==", r1.status_code)
        body1 = r1.json()
        print(json.dumps(body1, indent=2, ensure_ascii=False))

        # Cenário 4 — mesmo contacto (mesmo e-mail), nova oportunidade
        r2 = await client.post(
            "/contacts/leads",
            json={
                "name": "Mariana Silva",
                "email": email,
                "phone": phone,
                "source": "site",
                "message": "Agora quero crédito habitação.",
            },
        )
        print("\n== Cenário 4: contacto existente, nova lead ==", r2.status_code)
        body2 = r2.json()
        print(json.dumps(body2, indent=2, ensure_ascii=False))

        # Validação — sem e-mail e sem telefone deve ser rejeitado (422)
        r3 = await client.post(
            "/contacts/leads",
            json={"name": "Sem Contacto", "source": "manual"},
        )
        print("\n== Validação: sem email e sem telefone ==", r3.status_code)

        # Asserções rápidas
        assert r1.status_code == 201, r1.text
        assert body1["contact_reused"] is False
        assert body1["lead"]["status"] == "nova"
        assert body1["lead"]["responsible_area"] == "inside_sales"

        assert r2.status_code == 201, r2.text
        assert body2["contact_reused"] is True
        assert body2["contact"]["id"] == body1["contact"]["id"], "deveria reutilizar o contacto"
        assert body2["lead"]["id"] != body1["lead"]["id"], "deveria ser uma nova lead"

        assert r3.status_code == 422, r3.text

        print("\n[OK] Cenários 1, 4 e validação passaram.")


if __name__ == "__main__":
    asyncio.run(main())
