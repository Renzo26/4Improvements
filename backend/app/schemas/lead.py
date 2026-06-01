import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.enums import (
    HistoryActionType,
    InteractionType,
    LeadInterest,
    LeadSource,
    LeadStatus,
    ResponsibleArea,
    SlaStatus,
)


class LeadCreate(BaseModel):
    """Dados de entrada para registar uma nova lead.

    Regra obrigatória: `name` é exigido e deve existir pelo menos um meio de
    contacto (`email` OU `phone`).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Mariana Silva",
                "email": "mariana@email.com",
                "phone": "+351912345678",
                "source": "meta_ads",
                "campaign": "compradores_lisboa",
                "message": "Pretendo comprar apartamento em Lisboa.",
            }
        }
    )

    name: str = Field(min_length=1, max_length=200, description="Nome do potencial cliente.")
    email: Optional[EmailStr] = Field(default=None, description="E-mail. Obrigatório se não houver telefone.")
    phone: Optional[str] = Field(default=None, max_length=30, description="Telefone. Obrigatório se não houver e-mail.")
    source: LeadSource = Field(description="Origem da oportunidade.")
    campaign: Optional[str] = Field(default=None, max_length=200, description="Campanha de marketing (opcional).")
    utm_source: Optional[str] = Field(default=None, max_length=200)
    utm_medium: Optional[str] = Field(default=None, max_length=200)
    utm_campaign: Optional[str] = Field(default=None, max_length=200)
    message: Optional[str] = Field(default=None, description="Mensagem inicial livre do cliente.")

    @field_validator("phone", "campaign", "utm_source", "utm_medium", "utm_campaign", "message")
    @classmethod
    def _empty_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def _require_email_or_phone(self) -> "LeadCreate":
        if not self.email and not self.phone:
            raise ValueError("Informe pelo menos e-mail ou telefone.")
        return self


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: Optional[str]
    phone: Optional[str]
    created_at: datetime


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contact_id: uuid.UUID
    source: LeadSource
    campaign: Optional[str]
    utm_source: Optional[str]
    utm_medium: Optional[str]
    utm_campaign: Optional[str]
    message: Optional[str]
    status: LeadStatus
    responsible_area: ResponsibleArea
    interest: Optional[LeadInterest]
    sla_status: Optional[SlaStatus]
    created_at: datetime
    first_contact_at: Optional[datetime]
    qualified_at: Optional[datetime]
    routed_at: Optional[datetime]


class LeadCreatedResponse(BaseModel):
    """Resposta da criação: deixa explícito se o contacto foi reutilizado."""

    lead: LeadRead
    contact: ContactRead
    contact_reused: bool


class FirstContactCreate(BaseModel):
    """Regista o primeiro contacto com a lead (mede o SLA de 30 min)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"type": "chamada", "note": "Cliente respondeu e confirmou interesse em compra."}
        }
    )

    type: InteractionType = Field(description="Canal do contacto: chamada, whatsapp ou email.")
    note: Optional[str] = Field(default=None, max_length=2000, description="Observação opcional.")

    @field_validator("note")
    @classmethod
    def _empty_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


class QualificationCreate(BaseModel):
    """Qualifica a lead com o interesse identificado e dispara o roteamento."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"interest": "comprar_imovel", "note": "Interesse confirmado em compra de imóvel."}
        }
    )

    interest: LeadInterest = Field(description="Interesse identificado — determina a área de encaminhamento.")
    note: Optional[str] = Field(default=None, max_length=2000, description="Observação opcional.")

    @field_validator("note")
    @classmethod
    def _empty_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


class LeadHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_id: uuid.UUID
    action_type: HistoryActionType
    previous_status: Optional[LeadStatus]
    new_status: Optional[LeadStatus]
    previous_area: Optional[ResponsibleArea]
    new_area: Optional[ResponsibleArea]
    note: Optional[str]
    created_at: datetime


class LeadWithContactRead(LeadRead):
    """LeadRead com o contacto embedido — usado nas listagens e detalhes."""

    contact: ContactRead


class SlaCheckResponse(BaseModel):
    """Resultado da varredura de SLA (consumida pelo n8n no Fluxo 3)."""

    breached_count: int
    leads: list[LeadRead]
