import uuid
from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AlcadaDiscountRule(Base):
    """
    Desconto aplicado à comissão do GN conforme o tipo de alçada (taxa
    especial) usada no contrato.

    Espelha a aba `config_regras_alcada` — tabela pequena e estável, não é
    versionada por período.
    """

    __tablename__ = "alcada_discount_rules"
    __table_args__ = (UniqueConstraint("alcada", name="uq_alcada_discount_rules_alcada"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    alcada: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    desconto: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
