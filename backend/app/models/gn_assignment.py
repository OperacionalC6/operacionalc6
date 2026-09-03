import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GnAssignment(Base):
    """
    Quem é o GN (Gerente de Negócios) responsável por cada área, mês a mês.

    Espelha a aba `config_GNs` — organograma interno, muda quando um GN troca
    de área ou é substituído.
    """

    __tablename__ = "gn_assignments"
    __table_args__ = (UniqueConstraint("area", "ano", "mes", name="uq_gn_assignments_area_ano_mes"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    area: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    ano: Mapped[int] = mapped_column(nullable=False, index=True)
    mes: Mapped[int] = mapped_column(nullable=False, index=True)
    gn_responsavel: Mapped[str] = mapped_column(String(120), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
