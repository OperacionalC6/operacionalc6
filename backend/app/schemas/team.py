import uuid
from datetime import datetime

from pydantic import BaseModel


class TeamOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TeamCreate(BaseModel):
    name: str
    description: str | None = None
