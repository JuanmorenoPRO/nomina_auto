from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración por variables de entorno / .env (nunca credenciales en código)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./nomina_dev.sqlite3"

    @field_validator("database_url")
    @classmethod
    def _fix_postgres_driver(cls, v: str) -> str:
        # Railway inyecta postgresql:// o postgres://; psycopg3 necesita +psycopg
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v
    cors_origins: str = "http://localhost:5174"
    duracion_sesion_horas: int = 12
    cookie_segura: bool = False  # True en producción (HTTPS)
    static_dir: str = ""  # vacío en dev; en prod = /app/frontend/dist
    nomina_admin_email: str = ""  # si se setea, crea el admin al primer arranque
    nomina_admin_password: str = ""


@lru_cache
def settings() -> Settings:
    return Settings()
