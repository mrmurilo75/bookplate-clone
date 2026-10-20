from alembic import context
from sqlmodel import SQLModel

from bookplate import models  # noqa: F401  (registers the tables)
from bookplate.config import config as app_config
from bookplate.db import make_engine

url = context.config.get_main_option("sqlalchemy.url") or app_config.database_url
target_metadata = SQLModel.metadata

if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with make_engine(url).connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
