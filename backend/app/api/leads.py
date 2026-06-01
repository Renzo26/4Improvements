import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.enums import LeadStatus, ResponsibleArea, SlaStatus
from app.schemas.lead import (
    ContactRead,
    FirstContactCreate,
    LeadCreate,
    LeadCreatedResponse,
    LeadHistoryRead,
    LeadRead,
    QualificationCreate,
    SlaCheckResponse,
)
from app.services import lead_service

router = APIRouter(tags=["leads"])


@router.post(
    "/contacts/leads",
    response_model=LeadCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar nova lead (cria ou reutiliza o contacto)",
)
async def create_lead(
    payload: LeadCreate,
    db: AsyncSession = Depends(get_db),
) -> LeadCreatedResponse:
    lead, contact, contact_reused = await lead_service.create_lead(db, payload)
    return LeadCreatedResponse(
        lead=LeadRead.model_validate(lead),
        contact=ContactRead.model_validate(contact),
        contact_reused=contact_reused,
    )


@router.post(
    "/leads/{lead_id}/first-contact",
    response_model=LeadRead,
    summary="Registar o primeiro contacto e calcular o SLA (30 min)",
    description=(
        "Regista o 1.º contacto da equipa com a lead. Muda o estado para `contactada`, "
        "calcula `dentro_sla`/`fora_sla` (relógio do banco), cria a interação e grava o histórico."
    ),
    responses={
        404: {"description": "Lead não encontrada."},
        409: {"description": "Lead já teve o primeiro contacto registado."},
    },
)
async def register_first_contact(
    lead_id: uuid.UUID,
    payload: FirstContactCreate,
    db: AsyncSession = Depends(get_db),
) -> LeadRead:
    lead = await lead_service.register_first_contact(db, lead_id, payload)
    return LeadRead.model_validate(lead)


@router.post(
    "/leads/{lead_id}/qualification",
    response_model=LeadRead,
    summary="Qualificar a lead pelo interesse e encaminhar para a área",
    description=(
        "Qualifica a lead com o interesse e, na mesma transação, encaminha-a para a área "
        "correspondente (`comprar_imovel→buyer_advisory`, `vender_imovel→sell_advisor_mediacao`, "
        "`credito_habitacao→credito_habitacao`, `investimento_spv→spv_investimentos`). "
        "Muda o estado `→ qualificada → encaminhada` e grava dois registos no histórico."
    ),
    responses={
        404: {"description": "Lead não encontrada."},
        409: {"description": "Lead já foi encaminhada."},
    },
)
async def qualify_lead(
    lead_id: uuid.UUID,
    payload: QualificationCreate,
    db: AsyncSession = Depends(get_db),
) -> LeadRead:
    lead = await lead_service.qualify_lead(db, lead_id, payload)
    return LeadRead.model_validate(lead)


@router.post(
    "/leads/sla/check",
    response_model=SlaCheckResponse,
    summary="Varrer leads sem 1.º contacto há >30 min e marcá-las fora do SLA",
)
async def check_sla(
    db: AsyncSession = Depends(get_db),
) -> SlaCheckResponse:
    leads = await lead_service.check_sla_breaches(db)
    return SlaCheckResponse(
        breached_count=len(leads),
        leads=[LeadRead.model_validate(lead) for lead in leads],
    )


@router.get(
    "/leads",
    response_model=list[LeadRead],
    summary="Listar leads com filtros opcionais",
    description=(
        "Lista leads (mais recentes primeiro) com filtros opcionais por `status`, "
        "`responsible_area` e `sla_status`, mais paginação (`limit`/`offset`). "
        "Ex.: `?responsible_area=buyer_advisory` mostra as leads encaminhadas para Buyer Advisory."
    ),
)
async def list_leads(
    status: Optional[LeadStatus] = None,
    responsible_area: Optional[ResponsibleArea] = None,
    sla_status: Optional[SlaStatus] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[LeadRead]:
    leads = await lead_service.list_leads(
        db,
        status=status,
        responsible_area=responsible_area,
        sla_status=sla_status,
        limit=limit,
        offset=offset,
    )
    return [LeadRead.model_validate(lead) for lead in leads]


@router.get(
    "/leads/{lead_id}",
    response_model=LeadRead,
    summary="Obter uma lead pelo id",
    responses={404: {"description": "Lead não encontrada."}},
)
async def get_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> LeadRead:
    lead = await lead_service.get_lead(db, lead_id)
    return LeadRead.model_validate(lead)


@router.get(
    "/leads/{lead_id}/history",
    response_model=list[LeadHistoryRead],
    summary="Obter o histórico (auditoria) de uma lead",
    responses={404: {"description": "Lead não encontrada."}},
)
async def get_lead_history(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[LeadHistoryRead]:
    history = await lead_service.get_lead_history(db, lead_id)
    return [LeadHistoryRead.model_validate(item) for item in history]
