"""Regras de negócio do fluxo de leads.

Concentra a lógica para que controllers (rotas) e integrações (n8n) fiquem finos.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.contact import Contact
from app.models.enums import (
    INTEREST_TO_AREA,
    HistoryActionType,
    LeadStatus,
    ResponsibleArea,
    SlaStatus,
)
from app.models.interaction import Interaction
from app.models.lead import Lead
from app.models.lead_history import LeadHistory
from app.schemas.lead import FirstContactCreate, LeadCreate, QualificationCreate

settings = get_settings()


async def _db_now(db: AsyncSession) -> datetime:
    """Hora atual segundo o **banco**.

    Usar sempre o relógio do Postgres evita misturar fontes de tempo (a app e
    o servidor podem ter relógios diferentes), o que falsearia o cálculo do SLA.
    """
    return (await db.execute(select(func.now()))).scalar_one()


async def _get_lead_or_404(db: AsyncSession, lead_id: uuid.UUID) -> Lead:
    lead = await db.get(Lead, lead_id)
    if lead is None:
        raise NotFoundError("Lead não encontrada.")
    return lead


async def _find_existing_contact(
    db: AsyncSession, email: Optional[str], phone: Optional[str]
) -> Optional[Contact]:
    """Procura um contacto já existente pelo mesmo e-mail OU telefone."""
    conditions = []
    if email:
        conditions.append(Contact.email == email)
    if phone:
        conditions.append(Contact.phone == phone)
    if not conditions:
        return None

    result = await db.execute(select(Contact).where(or_(*conditions)).limit(1))
    return result.scalar_one_or_none()


async def create_lead(
    db: AsyncSession, data: LeadCreate
) -> tuple[Lead, Contact, bool]:
    """Cria uma nova lead, reutilizando o contacto se já existir.

    Retorna (lead, contact, contact_reused).
    """
    email = str(data.email) if data.email else None

    contact = await _find_existing_contact(db, email, data.phone)
    contact_reused = contact is not None

    if contact is None:
        contact = Contact(name=data.name, email=email, phone=data.phone)
        db.add(contact)
        await db.flush()  # garante contact.id

    # Toda nova lead entra como `nova` e atribuída a `inside_sales`.
    lead = Lead(
        contact_id=contact.id,
        source=data.source,
        campaign=data.campaign,
        utm_source=data.utm_source,
        utm_medium=data.utm_medium,
        utm_campaign=data.utm_campaign,
        message=data.message,
        status=LeadStatus.nova,
        responsible_area=ResponsibleArea.inside_sales,
    )
    db.add(lead)
    await db.flush()  # garante lead.id

    # Ação crítica → histórico.
    db.add(
        LeadHistory(
            lead_id=lead.id,
            action_type=HistoryActionType.lead_criada,
            previous_status=None,
            new_status=LeadStatus.nova,
            previous_area=None,
            new_area=ResponsibleArea.inside_sales,
            note="Lead criada e atribuída a Inside Sales.",
        )
    )
    await db.flush()

    # Recarrega para popular valores gerados pelo banco (created_at, etc.).
    await db.refresh(lead)
    await db.refresh(contact)

    return lead, contact, contact_reused


async def register_first_contact(
    db: AsyncSession, lead_id: uuid.UUID, data: FirstContactCreate
) -> Lead:
    """Regista o primeiro contacto e calcula o SLA de 30 minutos.

    Transição: `nova` → `contactada`. O SLA é `dentro_sla` se o contacto
    ocorrer até `settings.sla_minutes` após a criação, senão `fora_sla`.
    """
    lead = await _get_lead_or_404(db, lead_id)

    if lead.first_contact_at is not None:
        raise ConflictError("Esta lead já teve o primeiro contacto registado.")

    now = await _db_now(db)
    elapsed = now - lead.created_at
    within_sla = elapsed <= timedelta(minutes=settings.sla_minutes)

    previous_status = lead.status
    lead.first_contact_at = now
    lead.sla_status = SlaStatus.dentro_sla if within_sla else SlaStatus.fora_sla
    lead.status = LeadStatus.contactada

    db.add(
        Interaction(
            lead_id=lead.id,
            type=data.type,
            note=data.note,
            contacted_at=now,
        )
    )
    db.add(
        LeadHistory(
            lead_id=lead.id,
            action_type=HistoryActionType.primeiro_contacto,
            previous_status=previous_status,
            new_status=LeadStatus.contactada,
            previous_area=lead.responsible_area,
            new_area=lead.responsible_area,
            note=(
                f"Primeiro contacto via {data.type.value}. "
                f"SLA: {lead.sla_status.value} "
                f"({int(elapsed.total_seconds() // 60)} min)."
            ),
        )
    )

    await db.flush()
    await db.refresh(lead)
    return lead


async def qualify_lead(
    db: AsyncSession, lead_id: uuid.UUID, data: QualificationCreate
) -> Lead:
    """Qualifica a lead e encaminha para a área correspondente ao interesse.

    Faz, numa transação só, qualificação (`→ qualificada`) e encaminhamento
    (`→ encaminhada`), aplicando a regra `INTEREST_TO_AREA`.
    """
    lead = await _get_lead_or_404(db, lead_id)

    if lead.status == LeadStatus.encaminhada:
        raise ConflictError("Esta lead já foi encaminhada.")

    now = await _db_now(db)
    previous_status = lead.status
    previous_area = lead.responsible_area

    # 1) Qualificação
    lead.interest = data.interest
    lead.qualified_at = now
    lead.status = LeadStatus.qualificada
    db.add(
        LeadHistory(
            lead_id=lead.id,
            action_type=HistoryActionType.qualificacao,
            previous_status=previous_status,
            new_status=LeadStatus.qualificada,
            previous_area=previous_area,
            new_area=previous_area,
            note=data.note or f"Interesse identificado: {data.interest.value}.",
        )
    )

    # 2) Encaminhamento (regra de negócio: interesse → área)
    new_area = INTEREST_TO_AREA[data.interest]
    lead.responsible_area = new_area
    lead.routed_at = now
    lead.status = LeadStatus.encaminhada
    db.add(
        LeadHistory(
            lead_id=lead.id,
            action_type=HistoryActionType.encaminhamento,
            previous_status=LeadStatus.qualificada,
            new_status=LeadStatus.encaminhada,
            previous_area=previous_area,
            new_area=new_area,
            note=f"Encaminhada para {new_area.value}.",
        )
    )

    await db.flush()
    await db.refresh(lead)
    return lead


async def check_sla_breaches(db: AsyncSession) -> list[Lead]:
    """Marca como `fora_sla` as leads `nova` sem primeiro contacto há >30 min.

    Idempotente: só apanha leads ainda sem `sla_status`. Devolve as afetadas
    para o n8n (Fluxo 3) notificar.
    """
    # `created_at < now() - 30 min`, tudo avaliado no relógio do banco.
    deadline = func.now() - timedelta(minutes=settings.sla_minutes)

    stmt = select(Lead).where(
        Lead.first_contact_at.is_(None),
        Lead.sla_status.is_(None),
        Lead.created_at < deadline,
    )
    leads = list((await db.execute(stmt)).scalars().all())

    for lead in leads:
        lead.sla_status = SlaStatus.fora_sla
        db.add(
            LeadHistory(
                lead_id=lead.id,
                action_type=HistoryActionType.sla_estourado,
                previous_status=lead.status,
                new_status=lead.status,
                previous_area=lead.responsible_area,
                new_area=lead.responsible_area,
                note=f"SLA de {settings.sla_minutes} min estourado sem primeiro contacto.",
            )
        )

    await db.flush()
    for lead in leads:
        await db.refresh(lead)
    return leads


async def get_lead(db: AsyncSession, lead_id: uuid.UUID) -> Lead:
    """Devolve uma lead pelo id (404 se não existir)."""
    return await _get_lead_or_404(db, lead_id)


async def list_leads(
    db: AsyncSession,
    status: Optional[LeadStatus] = None,
    responsible_area: Optional[ResponsibleArea] = None,
    sla_status: Optional[SlaStatus] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Lead]:
    """Lista leads com filtros opcionais, mais recentes primeiro."""
    stmt = select(Lead)
    if status is not None:
        stmt = stmt.where(Lead.status == status)
    if responsible_area is not None:
        stmt = stmt.where(Lead.responsible_area == responsible_area)
    if sla_status is not None:
        stmt = stmt.where(Lead.sla_status == sla_status)

    stmt = stmt.order_by(Lead.created_at.desc()).limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars().all())


async def get_lead_history(
    db: AsyncSession, lead_id: uuid.UUID
) -> list[LeadHistory]:
    """Devolve o histórico (auditoria) de uma lead, do mais antigo ao mais novo."""
    await _get_lead_or_404(db, lead_id)
    stmt = (
        select(LeadHistory)
        .where(LeadHistory.lead_id == lead_id)
        .order_by(LeadHistory.created_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())
