from dotenv import load_dotenv

load_dotenv()  # carrega o .env no os.environ antes de qualquer import da app

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import leads
from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import ConflictError, NotFoundError

settings = get_settings()

API_DESCRIPTION = """
API de **gestão inicial de leads** para uma imobiliária — MVP do teste técnico 4Improvements.

Gere o ciclo de vida de uma lead: **criação → primeiro contacto (SLA) → qualificação → encaminhamento**,
mantendo o histórico de cada ação.

### Regras de negócio principais
- Toda lead nasce com estado `nova` e área `inside_sales`.
- Deduplicação de contacto por **e-mail ou telefone** (o mesmo contacto pode ter várias leads).
- **SLA:** o primeiro contacto deve ocorrer em até 30 min após a criação (calculado pelo relógio do banco).
- O **interesse** identificado determina a **área** de encaminhamento.
- Ações críticas (criação, contacto, qualificação, encaminhamento) geram **histórico**.

> A qualificação e o encaminhamento são feitos no **mesmo endpoint** (`/leads/{id}/qualification`):
> identificar o interesse determina deterministicamente a área, então é uma única transação atómica.
"""

tags_metadata = [
    {"name": "leads", "description": "Criação, consulta, primeiro contacto, qualificação e histórico de leads."},
    {"name": "health", "description": "Verificações de saúde da aplicação e da base de dados."},
]

app = FastAPI(
    title="4Improvements — Lead Management API",
    version="1.0.0",
    description=API_DESCRIPTION,
    openapi_tags=tags_metadata,
    contact={"name": "Candidato — Teste 4Improvements"},
    license_info={"name": "Uso restrito — avaliação técnica"},
)


@app.exception_handler(NotFoundError)
async def _not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": exc.message},
    )


@app.exception_handler(ConflictError)
async def _conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": exc.message},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"https?://.*\.easypanel\.host",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(leads.router)


@app.get("/health", tags=["health"], summary="Saúde da aplicação")
async def health():
    return {"status": "ok"}


@app.get("/health/db", tags=["health"], summary="Saúde da conexão ao banco")
async def health_db():
    """Valida a conectividade com o Supabase (Session Pooler)."""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        return {"database": "ok", "result": result.scalar()}
