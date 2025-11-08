import os
from logging.config import fileConfig
from sqlalchemy import create_engine
from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Optionally override URL via env var
db_user = os.getenv("DB_USER", "user")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")

if db_user and db_password and db_name:
    db_url_parts = [f"postgresql://{db_user}:{db_password}"]
    db_host_port = ""
    if db_host:
        db_host_port += db_host
    if db_port:
        db_host_port += f":{db_port}"
    if db_host_port:
        db_url_parts.append(f"@{db_host_port}")
    db_url_parts.append(f"/{db_name}")
    
    sqlalchemy_url = "".join(db_url_parts)
    config.set_main_option("sqlalchemy.url", sqlalchemy_url)
elif os.getenv("DATABASE_URL"):
    # Heroku uses postgres:// but SQLAlchemy requires postgresql://
    database_url = os.getenv("DATABASE_URL")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    config.set_main_option("sqlalchemy.url", database_url)

# Add your model's MetaData object here for 'autogenerate'
# support. We are using raw SQL migrations, so keep empty.
target_metadata = None

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = create_engine(config.get_main_option("sqlalchemy.url"), future=True)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()