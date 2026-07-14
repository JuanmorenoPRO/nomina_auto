from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración por variables de entorno / .env (nunca credenciales en código)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./nomina_dev.sqlite3"
    cors_origins: str = "http://localhost:5174"
    duracion_sesion_horas: int = 12
    cookie_segura: bool = False  # True en producción (HTTPS)


@lru_cache
def settings() -> Settings:
    return Settings()
