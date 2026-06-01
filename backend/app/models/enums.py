"""Enums de domínio das leads.

Os valores são iguais aos nomes (snake_case) para que a persistência como
VARCHAR (native_enum=False) grave exatamente o código esperado pelo desafio.
"""

import enum


class LeadSource(str, enum.Enum):
    """Origem da oportunidade."""

    site = "site"
    meta_ads = "meta_ads"
    whatsapp = "whatsapp"
    portal = "portal"
    indicacao = "indicacao"
    manual = "manual"


class LeadStatus(str, enum.Enum):
    """Estado da lead ao longo do fluxo."""

    nova = "nova"
    contactada = "contactada"
    qualificada = "qualificada"
    encaminhada = "encaminhada"


class ResponsibleArea(str, enum.Enum):
    """Área responsável pela lead."""

    inside_sales = "inside_sales"
    buyer_advisory = "buyer_advisory"
    sell_advisor_mediacao = "sell_advisor_mediacao"
    credito_habitacao = "credito_habitacao"
    spv_investimentos = "spv_investimentos"


class LeadInterest(str, enum.Enum):
    """Interesse principal identificado na qualificação."""

    comprar_imovel = "comprar_imovel"
    vender_imovel = "vender_imovel"
    credito_habitacao = "credito_habitacao"
    investimento_spv = "investimento_spv"


class SlaStatus(str, enum.Enum):
    """Resultado do SLA do primeiro contacto (30 minutos)."""

    dentro_sla = "dentro_sla"
    fora_sla = "fora_sla"


class InteractionType(str, enum.Enum):
    """Tipo de contacto registado."""

    chamada = "chamada"
    whatsapp = "whatsapp"
    email = "email"


class HistoryActionType(str, enum.Enum):
    """Ações que geram registo no histórico da lead."""

    lead_criada = "lead_criada"
    primeiro_contacto = "primeiro_contacto"
    qualificacao = "qualificacao"
    encaminhamento = "encaminhamento"
    sla_estourado = "sla_estourado"


# Regra de negócio: o interesse identificado determina a área de encaminhamento.
INTEREST_TO_AREA: dict[LeadInterest, ResponsibleArea] = {
    LeadInterest.comprar_imovel: ResponsibleArea.buyer_advisory,
    LeadInterest.vender_imovel: ResponsibleArea.sell_advisor_mediacao,
    LeadInterest.credito_habitacao: ResponsibleArea.credito_habitacao,
    LeadInterest.investimento_spv: ResponsibleArea.spv_investimentos,
}
