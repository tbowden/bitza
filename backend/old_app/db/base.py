"""SQLAlchemy declarative base and model imports"""

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData


# Naming convention for constraints (helps with Alembic)
convention = {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
        }

metadata = MetaData(naming_convention = convention)

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models"""
    metadata = metadata

# Import all models here so Alembic can detect them
# This is crucial for autogenerate to work

from app.models.user import User # noqa: E402, F401


