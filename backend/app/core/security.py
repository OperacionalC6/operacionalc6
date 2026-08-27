from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()

TokenType = Literal["access", "refresh"]


def verify_google_id_token(token: str) -> dict[str, Any]:
    """
    Verifica um ID token emitido pelo Google Sign-In (assinatura, expiração, e que
    foi emitido para o nosso GOOGLE_OAUTH_CLIENT_ID). Levanta ValueError se inválido
    — quem chamar deve tratar isso como falha de autenticação (401), nunca deixar
    passar.
    """
    return google_id_token.verify_oauth2_token(
        token, google_requests.Request(), settings.google_oauth_client_id
    )


def create_token(subject: str, token_type: TokenType, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    if token_type == "access":
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    else:
        expire = now + timedelta(days=settings.refresh_token_expire_days)

    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
