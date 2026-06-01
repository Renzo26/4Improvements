import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Contact(Base):
    """A pessoa por trás das oportunidades.

    Não deve ser duplicada: o mesmo e-mail ou telefone reutiliza o contacto
    existente. Um contacto pode estar associado a várias leads.
    """

    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Unicidade garante a prevenção de duplicidade também no nível do banco.
    # Ambos são opcionais, mas a regra exige pelo menos um (validado na aplicação).
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    leads: Mapped[list["Lead"]] = relationship(  # noqa: F821
        "Lead", back_populates="contact", cascade="all, delete-orphan"
    )
