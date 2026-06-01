import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import HistoryActionType, LeadStatus, ResponsibleArea


class LeadHistory(Base):
    """Evento de auditoria das ações críticas realizadas numa lead.

    Ações rastreadas: criação, primeiro contacto, qualificação e encaminhamento.
    """

    __tablename__ = "lead_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[HistoryActionType] = mapped_column(
        SAEnum(HistoryActionType, native_enum=False, length=40), nullable=False
    )
    previous_status: Mapped[Optional[LeadStatus]] = mapped_column(
        SAEnum(LeadStatus, native_enum=False, length=40), nullable=True
    )
    new_status: Mapped[Optional[LeadStatus]] = mapped_column(
        SAEnum(LeadStatus, native_enum=False, length=40), nullable=True
    )
    previous_area: Mapped[Optional[ResponsibleArea]] = mapped_column(
        SAEnum(ResponsibleArea, native_enum=False, length=40), nullable=True
    )
    new_area: Mapped[Optional[ResponsibleArea]] = mapped_column(
        SAEnum(ResponsibleArea, native_enum=False, length=40), nullable=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lead: Mapped["Lead"] = relationship(  # noqa: F821
        "Lead", back_populates="history"
    )
