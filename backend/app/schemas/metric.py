import uuid
from datetime import date, datetime

from pydantic import BaseModel


class MetricOut(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID | None
    metric_date: date
    metric_name: str
    value: float
    dimensions: dict | None
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MetricFilter(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    metric_name: str | None = None
    team_id: uuid.UUID | None = None  # só é respeitado se o usuário tiver acesso total
