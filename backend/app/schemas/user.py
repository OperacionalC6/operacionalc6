import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    team_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: UserRole = UserRole.MEMBRO
    team_id: uuid.UUID | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    team_id: uuid.UUID | None = None
    is_active: bool | None = None
