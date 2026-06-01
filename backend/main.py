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

app = FastAPI(
    title="4Improvements — Lead Management API",
    version="0.1.0",
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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db():
    """Valida a conectividade com o Supabase (Session Pooler)."""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        return {"database": "ok", "result": result.scalar()}
