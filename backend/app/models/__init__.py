"""Registo central dos models — importado pelo Alembic para o autogenerate."""

from app.models.contact import Contact
from app.models.interaction import Interaction
from app.models.lead import Lead
from app.models.lead_history import LeadHistory

__all__ = ["Contact", "Lead", "Interaction", "LeadHistory"]
