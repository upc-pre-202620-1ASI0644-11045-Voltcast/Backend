from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.persistence.configuration.column_types import TinyInt
from shared.infrastructure.persistence.configuration.database_configuration import Base

ROLE_ADMIN = "ADMIN"  # Supervisor
ROLE_USER = "USER"    # Ingeniero de Planta


class Role(Base):
    """
    Catálogo de roles del sistema.
    ADMIN (Supervisor), USER (Ingeniero de Planta).
    """
    __tablename__ = "role"

    id: Mapped[int] = mapped_column(TinyInt, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
