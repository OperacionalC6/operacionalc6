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
    status: Mapped[PipelineStatus] = mapped_column(
        Enum(PipelineStatus, name="pipeline_status"), nullable=False, default=PipelineStatus.RUNNING
    )
    trigger: Mapped[PipelineTrigger] = mapped_column(
        Enum(PipelineTrigger, name="pipeline_trigger"), nullable=False, default=PipelineTrigger.SCHEDULE
    )

    records_ingested: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
