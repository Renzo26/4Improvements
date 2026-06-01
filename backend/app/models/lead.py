import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    LeadInterest,
    LeadSource,
    LeadStatus,
    ResponsibleArea,
    SlaStatus,
)


class Lead(Base):
    """Cada nova oportunidade comercial associada a um contacto.

    Entra sempre com estado `nova` e área `inside_sales`. Cada lead tem o seu
    próprio histórico e interações, independente das demais leads do contacto.
    """

    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Dados de origem / rastreio
    source: Mapped[LeadSource] = mapped_column(
        SAEnum(LeadSource, native_enum=False, length=40), nullable=False
    )
    campaign: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    utm_source: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    utm_medium: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    utm_campaign: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Estado do fluxo
    status: Mapped[LeadStatus] = mapped_column(
        SAEnum(LeadStatus, native_enum=False, length=40),
        nullable=False,
        default=LeadStatus.nova,
    )
    responsible_area: Mapped[ResponsibleArea] = mapped_column(
        SAEnum(ResponsibleArea, native_enum=False, length=40),
        nullable=False,
        default=ResponsibleArea.inside_sales,
    )
    interest: Mapped[Optional[LeadInterest]] = mapped_column(
        SAEnum(LeadInterest, native_enum=False, length=40), nullable=True
    )
    sla_status: Mapped[Optional[SlaStatus]] = mapped_column(
        SAEnum(SlaStatus, native_enum=False, length=40), nullable=True
    )

    # Marcos temporais
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    first_contact_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    qualified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    routed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relacionamentos
    contact: Mapped["Contact"] = relationship(  # noqa: F821
        "Contact", back_populates="leads"
    )
    interactions: Mapped[list["Interaction"]] = relationship(  # noqa: F821
        "Interaction",
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="Interaction.contacted_at",
    )
    history: Mapped[list["LeadHistory"]] = relationship(  # noqa: F821
        "LeadHistory",
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="LeadHistory.created_at",
    )
