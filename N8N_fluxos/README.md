# Camada de Orquestração n8n — 4Improvements

Esta pasta contém os três workflows do **n8n** que formam a camada de **integração e orquestração** do sistema de gestão de leads. Eles **não contêm regra de negócio** — toda decisão (deduplicação, SLA, roteamento, transições de estado) vive no backend FastAPI. O n8n apenas **recebe eventos, orquestra a IA, agenda tarefas e notifica**, chamando o backend por HTTP.

> **Nota de escopo:** IA, WhatsApp e deploy estão listados como *fora do escopo obrigatório* no enunciado. Estes fluxos são um **extra demonstrativo** das competências da vaga (Especialista em n8n + IA), construídos **por cima** do backend que cumpre, sozinho, todos os requisitos obrigatórios.

- **Instância n8n:** `https://n8n.cloudysolutions.fun`
- **Backend chamado pelos fluxos:** `https://portfloio-4-improvements.e4xqua.easypanel.host`

---

## Visão geral

```
                         ┌───────────────────────── n8n ─────────────────────────┐
   Canal (site,          │                                                        │
   Meta Ads, etc.)  ──▶  │  FLUXO 1 ──(chama)──▶ FLUXO 2          FLUXO 3 (timer) │
        POST             │  ingestão            qualificação IA    monitor de SLA │
                         └────┬──────────────────────┬────────────────────┬──────┘
                              │ HTTP                  │ HTTP               │ HTTP
                              ▼                       ▼                    ▼
                         ┌──────────────────── Backend FastAPI ──────────────────┐
                         │  POST /contacts/leads   POST /leads/{id}/qualification │
                         │                         POST /leads/sla/check          │
                         └───────────────────────────┬────────────────────────────┘
                                                      ▼
                                            Supabase PostgreSQL
```

| Fluxo | Gatilho | Função | Endpoint do backend |
|---|---|---|---|
| **1 — Ingestão** | Webhook `POST /lead-intake` | Valida, deduplica e cria a lead | *(escreve direto no Postgres¹)* |
| **2 — Qualificação IA** | Webhook `POST /lead-qualify` | IA classifica o interesse e qualifica | `POST /leads/{id}/qualification` |
| **3 — SLA** | Schedule (a cada X min) | Deteta leads atrasadas e notifica | `POST /leads/sla/check` |

> ¹ O Fluxo 1 foi construído primeiro, ainda na fase de validação, escrevendo direto no Postgres via nós Postgres. A evolução natural (e recomendada) é trocar esses nós por uma chamada a `POST /contacts/leads` no backend — a lógica de dedup/criação já existe lá. Ver *Evolução* no fim.

---

## Fluxo 1 — Ingestão (`Fluxo 1 — ingestão (1).json`)

Recebe uma nova lead de um canal, valida os campos e grava (contacto + lead + histórico), reutilizando o contacto se já existir.

### Nós

| # | Nó | Tipo | Papel |
|---|---|---|---|
| 1 | **Recebe Dados** | Webhook | `POST /lead-intake`, responde via Respond node |
| 2 | **Checa campos obrigatórios Nome/source** | IF (AND) | Exige `name` **e** `source` |
| 3 | **Checa email ou telefone** | IF (OR) | Exige `email` **ou** `phone` (pelo menos um) |
| 4 | **Verifica se o contato já existe** | Postgres | `SELECT` por `email` OU `phone` |
| 5 | **If** | IF | Contacto encontrado? (`id` não vazio) |
| 6 | **Cria contato** | Postgres | `INSERT` (ramo "não existe"), com `NULLIF(...,'')` |
| 7 | **Cria Lead** | Postgres | `INSERT` lead (`status=nova`, `area=inside_sales`) |
| 8 | **Cria histórico** | Postgres | `INSERT` histórico `lead_criada` |
| 9 | **Respond to Webhook** | Respond | `201` com `lead_id`, `contact_id`, `status` |

### Regras de validação (replicam o backend)
- **Obrigatórios:** `name` **e** `source`, mais **pelo menos um** de `email`/`phone` → senão responde `400`.
- **Campos opcionais** (`campaign`, `utm_*`, `message`) usam `NULLIF(valor, '')` para gravar `NULL` em vez de string vazia — evita falso duplicado no `UNIQUE(email)`/`UNIQUE(phone)` e mantém os dados limpos.

### Payload de entrada (exemplo)
```json
{
  "name": "Mariana Silva",
  "email": "mariana@email.com",
  "phone": "+351912345678",
  "source": "meta_ads",
  "campaign": "compradores_lisboa",
  "message": "Pretendo comprar apartamento em Lisboa."
}
```

### Resposta (`201`)
```json
{
  "message": "Lead criada com sucesso",
  "lead_id": "…",
  "contact_id": "…",
  "status": "nova",
  "responsible_area": "inside_sales"
}
```

---

## Fluxo 2 — Agente de IA Classificador (`Fluxo 2 - Agente de IA Classificador.json`)

Recebe uma lead já existente e usa um LLM para **inferir o interesse** a partir da mensagem livre, depois chama o backend para **qualificar e encaminhar**.

### Nós

| # | Nó | Tipo | Papel |
|---|---|---|---|
| 1 | **Webhook** | Webhook | `POST /lead-qualify`, recebe `lead_id` + `message` |
| 2 | **AI Agent** | LangChain Agent | Classifica a mensagem num código de interesse |
| — | **OpenAI Chat Model** | LLM | Modelo `gpt-4.1-mini` (subnó do agente) |
| — | **Redis Chat Memory** | Memória | Contexto da conversa (TTL 24 h) |
| 3 | **HTTP Request** | HTTP | `POST /leads/{lead_id}/qualification` |
| 4 | **Respond to Webhook** | Respond | Devolve `lead_id`, `interest`, `responsible_area`, `status` |

### Prompt do classificador (system message)
O agente é instruído a responder **apenas** com JSON estrito:
```
{"interest": "<código>"}
```
onde `<código>` ∈ `comprar_imovel | vender_imovel | credito_habitacao | investimento_spv`.

> Forçar JSON estruturado torna o parsing fiável: o `output` do agente já é exatamente o corpo esperado pelo backend, então o nó HTTP usa `jsonBody = {{ $json.output }}` diretamente.

### Decisão importante — quem aplica o roteamento
A IA **só identifica o interesse**. A regra `interesse → área` (ex.: `comprar_imovel → buyer_advisory`) é aplicada pelo **backend**, no `POST /leads/{id}/qualification`, que também muda o estado (`qualificada → encaminhada`) e grava o histórico. Assim a regra fica testável (pytest) e independente do n8n.

### Payload de entrada (exemplo)
```json
{ "lead_id": "…", "message": "Quero vender a minha casa no Porto." }
```

### Resposta (exemplo)
```json
{
  "lead_id": "…",
  "interest": "vender_imovel",
  "responsible_area": "sell_advisor_mediacao",
  "status": "encaminhada"
}
```

### Credenciais usadas
- **OpenAI account** (chave da OpenAI, configurada no n8n)
- **Redis account** (memória de conversa)

---

## Fluxo 3 — SLA (`Fluxo 3 — SLA.json`)

Corre periodicamente, pede ao backend para marcar as leads que estouraram o SLA de 30 min e **notifica a equipa por WhatsApp**.

### Nós

| # | Nó | Tipo | Papel |
|---|---|---|---|
| 1 | **Schedule Trigger** | Schedule | Dispara em intervalo de minutos (ex.: a cada 5 min) |
| 2 | **HTTP Request** | HTTP | `POST /leads/sla/check` |
| 3 | **If** | IF | `breached_count > 0`? |
| 4 | **Send a text message** | WAHA | Envia o alerta no WhatsApp (sessão `Cloudy`) |

### Por que polling (Schedule) e não "esperar 30 min" por lead
Pendurar um *wait* de 30 min em cada lead é frágil (perde estado se o n8n reinicia, não escala). O Schedule + endpoint idempotente é robusto: o backend só apanha leads ainda sem `sla_status`, então **não notifica a mesma lead duas vezes**.

### Onde mora a regra dos 30 min
No **backend** (`/leads/sla/check`), calculada com o **relógio do Postgres** (`created_at < now() - 30 min`). O n8n só agenda e notifica.

### Resposta do backend consumida
```json
{ "breached_count": 1, "leads": [ { "id": "…", "source": "meta_ads", "created_at": "…", "sla_status": "fora_sla" } ] }
```

### Mensagem WhatsApp (montada no nó WAHA)
```
🚨 *Alerta de SLA — 4Improvements*

1 lead(s) ultrapassaram os 30 min sem primeiro contacto:

• 2542e735 | origem: meta_ads | criada: 01/06/2026, 00:24:15

⚠️ Contactar com urgência.
```

### Credenciais usadas
- **WAHA account** (WhatsApp HTTP API self-hosted) — sessão `Cloudy`, destino `5511987278746`

---

## Como os fluxos se conectam

- **Fluxo 1 → Fluxo 2:** ao criar a lead, o Fluxo 1 pode chamar o webhook do Fluxo 2 (`/lead-qualify`) passando `lead_id` + `message`, disparando a **pré-qualificação automática por IA** logo na entrada. *(Ligação recomendada; ver Evolução.)*
- **Fluxo 3** é independente — corre por agenda, não depende dos outros.

> **Nota sobre a sequência do enunciado:** o fluxo "oficial" é *criação → primeiro contacto → qualificação*. A pré-qualificação por IA na entrada é um **atalho de produtividade**: a IA sugere o interesse a partir da mensagem inicial; o **primeiro contacto humano e o SLA de 30 min continuam a ser uma ação separada**, registada via `POST /leads/{id}/first-contact`. Uma lead pode estar `encaminhada` (pela IA) e ainda assim ser sinalizada `fora_sla` se ninguém a contactar a tempo — o sistema não confunde "qualificada pela IA" com "contactada por uma pessoa".

---

## URLs dos webhooks

| Fluxo | Teste | Produção |
|---|---|---|
| 1 — Ingestão | `…/webhook-test/lead-intake` | `…/webhook/lead-intake` |
| 2 — Qualificação | `…/webhook-test/lead-qualify` | `…/webhook/lead-qualify` |

(base: `https://n8n.cloudysolutions.fun`)

---

## Evolução recomendada

1. **Fluxo 1 → backend:** trocar os nós Postgres por uma única chamada `POST /contacts/leads`, centralizando a dedup/criação no código testável (hoje a lógica está duplicada entre o SQL do n8n e o `lead_service.py`).
2. **Encadear 1 → 2:** adicionar no fim do Fluxo 1 um HTTP Request para `/lead-qualify`, tornando a qualificação automática.
3. **Autenticação:** proteger os webhooks (header secret) e o backend (API key), hoje abertos para facilitar a avaliação.
4. **Segurança SQL:** enquanto o Fluxo 1 usar nós Postgres, migrar de interpolação de string para *query parameters* (`$1, $2…`) para eliminar risco de injeção.
