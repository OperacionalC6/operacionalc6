import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"      # acesso total + gestão do sistema (ex: você)
    GESTOR = "gestor"    # acesso total de leitura a todas as áreas
    MEMBRO = "membro"    # acesso restrito à sua própria área/equipe

    @property
    def has_full_access(self) -> bool:
        return self in (UserRole.ADMIN, UserRole.GESTOR)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Não guardamos senha — login é só via Google Sign-In (ver security-access skill).
    # Um usuário só consegue entrar se já existir aqui com is_active=True; é assim que
    # a "lista de e-mails autorizados" é implementada: cadastro pelo admin, não senha.
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        # values_callable: sem isso, o SQLAlchemy manda o NOME do membro Python
        # ("ADMIN") pro Postgres em vez do VALOR ("admin"), que é o que a migration
        # criou no tipo `user_role` — dá erro "invalid input value" ao gravar
        # (confirmado tentando rodar o seed contra o banco real).
        Enum(UserRole, name="user_role", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
        default=UserRole.MEMBRO,
    )

    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    team: Mapped["Team"] = relationship(back_populates="users")  # noqa: F821

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
