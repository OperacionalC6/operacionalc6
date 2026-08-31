import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PipelineStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class PipelineTrigger(str, enum.Enum):
    SCHEDULE = "schedule"
    MANUAL = "manual"


class PipelineRun(Base):
    """Histórico de execuções de ingestão de dados (RPA ou API Corban)."""

    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    source: Mapped[str] = mapped_column(String(50), nullable=False)  # "api_corban" | "portal_rpa"
    # values_callable: mesmo motivo do User.role (ver models/user.py) — sem isso o
    # SQLAlchemy manda o NOME do membro Python em vez do VALOR, que não bate com
    # os tipos enum que a migration criou no Postgres.
    status: Mapped[PipelineStatus] = mapped_column(
        Enum(
            PipelineStatus,
            name="pipeline_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=PipelineStatus.RUNNING,
    )
    trigger: Mapped[PipelineTrigger] = mapped_column(
        Enum(
            PipelineTrigger,
            name="pipeline_trigger",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=PipelineTrigger.SCHEDULE,
    )

    records_ingested: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
