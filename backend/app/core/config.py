from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Banco de dados — Supabase (Session Pooler, porta 5432, IPv4)
    database_url: str

    # App
    app_env: str = "development"
    app_port: int = 8080

    # SLA — minutos para o primeiro contacto a partir da criação da lead
    sla_minutes: int = 30

    # CORS — origem do frontend (Lovable em dev / domínio em produção)
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
