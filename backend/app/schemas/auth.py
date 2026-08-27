from pydantic import BaseModel


class GoogleLoginRequest(BaseModel):
    # ID token (JWT) que o Google Identity Services devolve pro frontend depois do
    # usuário escolher a conta — não é senha nem código, é assinado pelo Google.
    id_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
