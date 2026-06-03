"""Semeia leads JÁ fora do SLA para demonstrar o Fluxo 3 (alerta WhatsApp).

Insere 3 contactos + 3 leads com `created_at` no passado (por omissão, 40 min),
estado `nova` e sem primeiro contacto — exatamente as condições que o endpoint
`POST /leads/sla/check` apanha. Depois de correr este script, chame o endpoint
(ou deixe o Schedule do n8n correr) para marcar as leads como `fora_sla` e
disparar a notificação por WhatsApp.

Uso:
    python -m scripts.seed_sla_breaches            # 3 leads, 40 min atrás, offset 0
    python -m scripts.seed_sla_breaches 5 90       # 5 leads, 90 min atrás
    python -m scripts.seed_sla_breaches 2 2 3      # 2 leads, 2 min atrás, a partir da persona #3
"""

import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

from app.core.database import AsyncSessionLocal
from app.models.contact import Contact
from app.models.enums import HistoryActionType, LeadSource, LeadStatus, ResponsibleArea
from app.models.lead import Lead
from app.models.lead_history import LeadHistory

# Personas fictícias para a demo (telefones distintos para não colidirem).
PERSONAS = [
    ("Helena Castro", "meta_ads", "Tenho interesse em comprar apartamento em Lisboa."),
    ("Tiago Ferreira", "site", "Quero vender a minha moradia em Cascais."),
    ("Sofia Marques", "portal", "Preciso de simulação de crédito habitação."),
    ("Bruno Pereira", "whatsapp", "Procuro oportunidades de investimento em imóveis."),
    ("Carla Lopes", "indicacao", "Gostaria de avaliar a minha casa para venda."),
]


async def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    minutes_ago = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    offset = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    n = min(n, len(PERSONAS) - offset)

    # `created_at` no passado, no fuso UTC (coluna é timezone-aware).
    past = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    # Sufixo único por execução para não esbarrar na unicidade de email/phone.
    stamp = int(datetime.now().timestamp())

    created: list[tuple[str, uuid.UUID]] = []

    async with AsyncSessionLocal() as db:
        for i in range(offset, offset + n):
            name, source, message = PERSONAS[i]
            contact = Contact(
                name=name,
                email=f"sla.demo.{stamp}.{i}@email.com",
                phone=f"+35196{stamp % 10_000_000:07d}{i}",
                created_at=past,
            )
            db.add(contact)
            await db.flush()  # garante contact.id

            lead = Lead(
                contact_id=contact.id,
                source=LeadSource(source),
                campaign="demo_sla",
                message=message,
                status=LeadStatus.nova,
                responsible_area=ResponsibleArea.inside_sales,
                sla_status=None,          # ainda não avaliado
                first_contact_at=None,    # sem primeiro contacto
                created_at=past,          # << no passado: já estoura os 30 min
            )
            db.add(lead)
            await db.flush()  # garante lead.id

            db.add(
                LeadHistory(
                    lead_id=lead.id,
                    action_type=HistoryActionType.lead_criada,
                    new_status=LeadStatus.nova,
                    new_area=ResponsibleArea.inside_sales,
                    note="Lead semeada para demonstração de SLA (criada no passado).",
                    created_at=past,
                )
            )
            created.append((name, lead.id))

        await db.commit()

    print(f"[OK] {len(created)} leads semeadas com created_at {minutes_ago} min atrás:\n")
    for name, lead_id in created:
        print(f"  • {name:18} | lead_id = {lead_id}")
    print(
        "\nProximo passo: chame POST /leads/sla/check (Swagger) ou deixe o "
        "Schedule do n8n correr.\nO backend marcara estas leads como 'fora_sla' "
        "e o Fluxo 3 envia o alerta no WhatsApp."
    )


if __name__ == "__main__":
    asyncio.run(main())
