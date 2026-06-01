"""Testes automatizados dos comportamentos mínimos exigidos no enunciado (secção 12).

| Teste                                   | Resultado esperado                          |
|-----------------------------------------|---------------------------------------------|
| Criação de nova lead válida             | Lead criada corretamente                    |
| Criação sem e-mail e sem telefone       | Requisição rejeitada (422)                  |
| Nova lead com contacto já existente     | Contacto reutilizado, nova lead criada      |
| Primeiro contacto dentro de 30 minutos  | SLA identificado como dentro_sla            |
| Primeiro contacto após 30 minutos       | SLA identificado como fora_sla              |
| Qualificação de comprador               | Encaminhada para buyer_advisory             |
| Qualificação de vendedor                | Encaminhada para sell_advisor_mediacao      |
"""

import pytest

from tests.conftest import backdate_lead, create_lead, unique_email, unique_phone


async def test_criar_lead_valida(client):
    body = await create_lead(client)

    assert body["contact_reused"] is False
    assert body["lead"]["status"] == "nova"
    assert body["lead"]["responsible_area"] == "inside_sales"
    assert body["lead"]["interest"] is None
    assert body["lead"]["sla_status"] is None

    # A criação deve gerar histórico (ação lead_criada).
    hist = await client.get(f"/leads/{body['lead']['id']}/history")
    assert hist.status_code == 200
    acoes = [h["action_type"] for h in hist.json()]
    assert "lead_criada" in acoes


async def test_criar_lead_sem_email_e_sem_telefone_rejeita(client):
    resp = await client.post(
        "/contacts/leads",
        json={"name": "Sem Contacto", "source": "manual"},
    )
    assert resp.status_code == 422


async def test_contacto_existente_e_reutilizado(client):
    email = unique_email()
    phone = unique_phone()

    primeira = await create_lead(client, email=email, phone=phone)
    segunda = await create_lead(
        client, email=email, phone=phone, source="site", message="Agora quero crédito."
    )

    # Mesmo contacto, nova lead — históricos independentes.
    assert segunda["contact_reused"] is True
    assert segunda["contact"]["id"] == primeira["contact"]["id"]
    assert segunda["lead"]["id"] != primeira["lead"]["id"]


async def test_primeiro_contacto_dentro_do_sla(client):
    body = await create_lead(client)
    lead_id = body["lead"]["id"]

    resp = await client.post(
        f"/leads/{lead_id}/first-contact",
        json={"type": "chamada", "note": "Liguei e apresentei a empresa."},
    )
    assert resp.status_code == 200
    lead = resp.json()
    assert lead["status"] == "contactada"
    assert lead["sla_status"] == "dentro_sla"
    assert lead["first_contact_at"] is not None


async def test_primeiro_contacto_fora_do_sla(client):
    body = await create_lead(client)
    lead_id = body["lead"]["id"]

    # "Envelhece" a lead para 31 min atrás → estoura o SLA de 30 min.
    await backdate_lead(lead_id, minutes=31)

    resp = await client.post(
        f"/leads/{lead_id}/first-contact", json={"type": "email"}
    )
    assert resp.status_code == 200
    assert resp.json()["sla_status"] == "fora_sla"


async def test_qualificacao_comprador_encaminha_buyer_advisory(client):
    body = await create_lead(client)
    lead_id = body["lead"]["id"]

    resp = await client.post(
        f"/leads/{lead_id}/qualification", json={"interest": "comprar_imovel"}
    )
    assert resp.status_code == 200
    lead = resp.json()
    assert lead["interest"] == "comprar_imovel"
    assert lead["responsible_area"] == "buyer_advisory"
    assert lead["status"] == "encaminhada"

    # Histórico deve conter qualificação e encaminhamento.
    hist = await client.get(f"/leads/{lead_id}/history")
    acoes = [h["action_type"] for h in hist.json()]
    assert "qualificacao" in acoes
    assert "encaminhamento" in acoes


async def test_qualificacao_vendedor_encaminha_sell_advisor(client):
    body = await create_lead(client)
    lead_id = body["lead"]["id"]

    resp = await client.post(
        f"/leads/{lead_id}/qualification", json={"interest": "vender_imovel"}
    )
    assert resp.status_code == 200
    lead = resp.json()
    assert lead["responsible_area"] == "sell_advisor_mediacao"
    assert lead["status"] == "encaminhada"


# --- Casos extra (tratamento de erros / idempotência) ---------------------


async def test_lead_inexistente_devolve_404(client):
    resp = await client.get("/leads/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_primeiro_contacto_repetido_devolve_409(client):
    body = await create_lead(client)
    lead_id = body["lead"]["id"]

    primeiro = await client.post(
        f"/leads/{lead_id}/first-contact", json={"type": "chamada"}
    )
    assert primeiro.status_code == 200

    repetido = await client.post(
        f"/leads/{lead_id}/first-contact", json={"type": "email"}
    )
    assert repetido.status_code == 409
