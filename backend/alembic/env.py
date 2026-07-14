from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# La URL sale de la configuración de la app (variable de entorno / .env),
# nunca de alembic.ini, para no duplicar ni versionar credenciales.
from nomina.infraestructura.config import settings
from nomina.infraestructura.persistencia.base import Base
from nomina.infraestructura.persistencia import modelos  # noqa: F401  (registra las tablas)

config = context.config
config.set_main_option("sqlalchemy.url", settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
