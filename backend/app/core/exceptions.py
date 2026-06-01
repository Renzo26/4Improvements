"""Exceções de domínio.

A camada de serviço lança estes erros; a camada de API (rotas) traduz para
o código HTTP adequado. Assim as regras de negócio não dependem do FastAPI.
"""


class DomainError(Exception):
    """Erro de negócio com mensagem amigável."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(DomainError):
    """Recurso não encontrado (→ 404)."""


class ConflictError(DomainError):
    """Operação inválida para o estado atual do recurso (→ 409)."""
