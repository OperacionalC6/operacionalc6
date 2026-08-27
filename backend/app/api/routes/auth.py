from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_user
from app.core.security import create_token, decode_token, verify_google_id_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import GoogleLoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserOut
from app.services.audit import log_action
from app.services.rate_limit import (
    register_failed_attempt,
    reset_attempts,
    too_many_failed_attempts,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/google", response_model=TokenResponse)
def login_with_google(payload: GoogleLoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent")

    try:
        google_info = verify_google_id_token(payload.id_token)
    except ValueError:
        log_action(
            db,
            action="login_failed",
            ip_address=ip,
            user_agent=ua,
            extra={"reason": "google_token_invalido"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token do Google inválido.")

    email = (google_info.get("email") or "").lower()
    if not email or not google_info.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail do Google não verificado.",
        )

    if too_many_failed_attempts(email, ip):
        log_action(
            db,
            action="login_blocked_rate_limit",
            user_email_snapshot=email,
            ip_address=ip,
            user_agent=ua,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas de login. Tente novamente em alguns minutos.",
        )

    user = db.query(User).filter(User.email == email).first()

    if user is None or not user.is_active:
        register_failed_attempt(email, ip)
        log_action(
            db,
            action="login_denied_not_authorized",
            user_email_snapshot=email,
            ip_address=ip,
            user_agent=ua,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seu e-mail não está autorizado a acessar este sistema. Peça a um administrador para te cadastrar.",
        )

    reset_attempts(email, ip)

    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()

    access_token = create_token(str(user.id), "access", {"role": user.role.value})
    refresh_token = create_token(str(user.id), "refresh")

    log_action(
        db,
        action="login_success",
        user_id=user.id,
        user_email_snapshot=user.email,
        ip_address=ip,
        user_agent=ua,
    )

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    data = decode_token(payload.refresh_token)
    if data is None or data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido.")

    import uuid as _uuid

    user = db.get(User, _uuid.UUID(data["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido.")

    access_token = create_token(str(user.id), "access", {"role": user.role.value})
    new_refresh_token = create_token(str(user.id), "refresh")
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
