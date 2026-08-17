import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services.audit import log_action

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou expiradas.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_error

    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise credentials_error

    user_id = payload.get("sub")
    try:
        user = db.get(User, uuid.UUID(user_id))
    except (ValueError, TypeError):
        raise credentials_error

    if user is None or not user.is_active:
        raise credentials_error

    return user


def require_roles(*roles: UserRole):
    def _dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if current_user.role not in roles:
            log_action(
                db,
                action="access_denied",
                user_id=current_user.id,
                user_email_snapshot=current_user.email,
                resource_type="route",
                resource_id=str(request.url.path),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                extra={"required_roles": [r.value for r in roles], "actual_role": current_user.role.value},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para acessar este recurso.",
            )
        return current_user

    return _dependency


require_full_access = require_roles(UserRole.ADMIN, UserRole.GESTOR)
require_admin = require_roles(UserRole.ADMIN)
