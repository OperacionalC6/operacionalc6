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
    # Sem senha — o admin autoriza um e-mail, e a pessoa entra com "Login com Google"
    # usando esse mesmo e-mail. É assim que a lista de acesso é controlada.
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.MEMBRO
    team_id: uuid.UUID | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    team_id: uuid.UUID | None = None
    is_active: bool | None = None
