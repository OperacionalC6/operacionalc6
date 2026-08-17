from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_user
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserOut
from app.services.audit import log_action
from app.services.rate_limit import too_many_failed_attempts, register_failed_attempt, reset_attempts

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent")

    if too_many_failed_attempts(payload.email, ip):
        log_action(
            db,
            action="login_blocked_rate_limit",
            user_email_snapshot=payload.email,
            ip_address=ip,
            user_agent=ua,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas de login. Tente novamente em alguns minutos.",
        )

    user = db.query(User).filter(User.email == payload.email.lower()).first()

    if user is None or not verify_password(payload.password, user.hashed_password) or not user.is_active:
        register_failed_attempt(payload.email, ip)
        log_action(
            db,
            action="login_failed",
            user_id=user.id if user else None,
            user_email_snapshot=payload.email,
            ip_address=ip,
            user_agent=ua,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos.",
        )

    reset_attempts(payload.email, ip)

    from datetime import datetime, timezone

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


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta.")

    current_user.hashed_password = hash_password(payload.new_password)
    current_user.must_change_password = False
    db.add(current_user)
    db.commit()

    log_action(
        db,
        action="password_changed",
        user_id=current_user.id,
        user_email_snapshot=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
