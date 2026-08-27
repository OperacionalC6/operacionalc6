import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "test-client-id.apps.googleusercontent.com")

from app.core.security import create_token, decode_token  # noqa: E402


def test_access_token_roundtrip():
    token = create_token("user-123", "access", {"role": "admin"})
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert payload["role"] == "admin"


def test_decode_invalid_token_returns_none():
    assert decode_token("token-invalido") is None
