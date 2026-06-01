FROM python:3.11-slim

WORKDIR /app

# Variáveis de runtime saudáveis para Python em container
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# asyncpg/pydantic-core têm wheels para cp311 → não é preciso toolchain de compilação.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Aplica migrações pendentes (no-op se o banco já estiver em head) e sobe a API.
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8080"]
