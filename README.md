# 4Improvements — Gestão de Leads (MVP)

API de gestão de leads para uma imobiliária, com **arquitetura híbrida**:

- **Backend (Python / FastAPI)** — *fonte da verdade* das regras de negócio: deduplicação de contactos, SLA de primeiro contacto, qualificação e encaminhamento por área, histórico/auditoria.
- **n8n** — camada de *orquestração e integração*: ingestão via webhook, classificação do interesse por **IA (Anthropic)** e disparo do SLA. O n8n **não** contém regra de negócio — chama o backend via HTTP.
- **Supabase (PostgreSQL)** — persistência, acedido via *Session Pooler*.

> Trabalho desenvolvido como teste técnico para a vaga **Especialista em N8N e Infraestruturas de Inteligência Artificial**.

---

## Arquitetura

```
                 ┌──────────────────────── n8n ────────────────────────┐
   Lead  ──────▶ │ Fluxo 1: ingestão     Fluxo 2: IA      Fluxo 3: SLA │
 (webhook/site)  │   valida + cria         classifica        timer      │
                 └───────┬───────────────────┬──────────────────┬───────┘
                         │ HTTP              │ HTTP             │ HTTP
                         ▼                   ▼                  ▼
                 ┌──────────────────── Backend FastAPI ────────────────┐
                 │  Regras: dedup · SLA 30min · interesse→área · estado │
                 └───────────────────────────┬─────────────────────────┘
                                             ▼
                                   Supabase PostgreSQL
```

### Camadas (Clean Architecture)

```
backend/
├── main.py                  # bootstrap FastAPI + handlers de erro
├── app/
│   ├── api/                 # rotas (camada de entrada, "fina")
│   ├── services/            # regras de negócio (lead_service)
│   ├── schemas/             # contratos Pydantic (entrada/saída)
│   ├── models/              # entidades SQLAlchemy + enums
│   └── core/                # config, database, exceptions
└── alembic/                 # migrações de schema
```

---

## Modelo de domínio

| Entidade | Papel |
|---|---|
| **Contact** | Pessoa única (dedup por e-mail **ou** telefone). |
| **Lead** | Cada oportunidade. Um contacto pode ter várias leads. |
| **Interaction** | Contacto efetuado (ex.: o primeiro contacto). |
| **LeadHistory** | Auditoria das ações críticas. |

**Ciclo de estados:** `nova → contactada → qualificada → encaminhada`

**Regra de encaminhamento** (interesse → área):

| Interesse | Área responsável |
|---|---|
| `comprar_imovel` | `buyer_advisory` |
| `vender_imovel` | `sell_advisor_mediacao` |
| `credito_habitacao` | `credito_habitacao` |
| `investimento_spv` | `spv_investimentos` |

**SLA:** primeiro contacto deve ocorrer em até **30 min** após a criação. O cálculo usa sempre o **relógio do banco** (evita divergência entre app e servidor).

---

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/contacts/leads` | Cria lead (cria ou reutiliza o contacto). |
| `POST` | `/leads/{id}/first-contact` | Regista 1.º contacto e calcula o SLA. |
| `POST` | `/leads/{id}/qualification` | Qualifica pelo interesse e encaminha para a área. |
| `POST` | `/leads/sla/check` | Marca leads atrasadas como `fora_sla` (consumido pelo n8n). |
| `GET` | `/leads` | Lista com filtros (`status`, `responsible_area`, `sla_status`) + paginação. |
| `GET` | `/leads/{id}` | Detalhe de uma lead. |
| `GET` | `/leads/{id}/history` | Histórico/auditoria da lead. |
| `GET` | `/health` · `/health/db` | Saúde da app e da conexão ao banco. |

Documentação interativa (Swagger): `GET /docs`.

---

## Como rodar localmente

Requisitos: **Python 3.11** (asyncpg/pydantic-core têm wheels para 3.11).

```bash
cd backend
py -3.11 -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

copy .env.example .env          # preencher DATABASE_URL (Supabase Session Pooler)
alembic upgrade head            # aplica o schema (no-op se já existir)

uvicorn main:app --reload --port 8080
```

### Testes de fumaça

```bash
python -m scripts.smoke_create_lead   # criação + dedup + validação
python -m scripts.smoke_lifecycle     # ciclo completo: criação→contacto→qualificação→histórico
```

---

## Deploy (EasyPanel + Docker)

O serviço sobe a partir de [`docker-compose.yml`](docker-compose.yml) (rede externa `easypanel`). Variáveis necessárias no painel:

| Variável | Exemplo |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres.<ref>:<senha>@aws-1-<reg>.pooler.supabase.com:5432/postgres` |
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `SLA_MINUTES` | `30` |
| `CORS_ORIGINS` | URL do frontend |

O container roda `alembic upgrade head` no arranque e sobe o `uvicorn` na porta `8080`.

---

## n8n — fluxos

- **Fluxo 1 — Ingestão** ([`Fluxo 1 — ingestão (1).json`](Fluxo%201%20%E2%80%94%20ingest%C3%A3o%20(1).json)): webhook → validação (`name`+`source`, `email` **ou** `phone`) → dedup → cria lead + histórico.
- **Fluxo 2 — Qualificação por IA:** webhook → *Anthropic* classifica a mensagem no código de interesse → `POST /leads/{id}/qualification`.
- **Fluxo 3 — SLA:** *Schedule* → `POST /leads/sla/check` → notifica as atrasadas.

---

## Stack

FastAPI · SQLAlchemy 2 (async/asyncpg) · Alembic · Pydantic v2 · PostgreSQL (Supabase) · n8n · Anthropic · Docker.
