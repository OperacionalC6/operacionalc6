import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContractOverride(Base):
    """
    Ajuste manual pontual de filial por contrato (exceção — contrato que
    deveria contar pra uma filial diferente da que o sistema calcularia).

    Espelha a aba `config_AjustesContrato`. As demais colunas daquela aba
    (CHAVE_GN, GN_RESPONSAVEL, ANO, MES, CodLoja, CNPJ, etc.) são todas
    fórmulas derivadas de outras abas, não dado manual de verdade — só
    `Codigo Contrato` e `FILIAL_AJUSTADA` são entrada real; o resto é
    recalculado no serviço de `base_final`, não guardado aqui.
    """

    __tablename__ = "contract_overrides"
    __table_args__ = (UniqueConstraint("codigo_contrato", name="uq_contract_overrides_codigo_contrato"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    codigo_contrato: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    filial_ajustada: Mapped[str] = mapped_column(String(120), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
