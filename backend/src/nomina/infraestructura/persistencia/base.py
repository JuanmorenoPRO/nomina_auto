from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from nomina.infraestructura.config import settings


class Base(DeclarativeBase):
    pass


def crear_engine(url: str | None = None) -> Engine:
    url = url or settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def fabrica_sesiones(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


_engine: Engine | None = None
_sessionmaker: sessionmaker[Session] | None = None


def sesion() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por request, commit al éxito."""
    global _engine, _sessionmaker
    if _sessionmaker is None:
        _engine = crear_engine()
        _sessionmaker = fabrica_sesiones(_engine)
    with _sessionmaker() as session:
        yield session
        session.commit()
