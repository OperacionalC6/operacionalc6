from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    # database_url/jwt_secret_key/google_oauth_client_id: usados só pelo app
    # web antigo (FastAPI+Postgres), DESATIVADO em 2026-09-24 (pivô pra
    # automação local em Excel — ver skill project-context). Opcionais desde
    # 2026-10-13: exigi-los sempre travava QUALQUER script local (inclusive
    # atualizar_excel.py, que nunca os usa) se não estivessem setados como
    # variável de ambiente — achado real do usuário, que precisou inventar
    # valor fake só pra `Settings()` construir.
    database_url: str | None = None

    @field_validator("database_url")
    @classmethod
    def _use_psycopg3_driver(cls, v: str | None) -> str | None:
        # Provedores gerenciados (Render, etc.) entregam a connection string sem
        # driver explícito, e às vezes no esquema curto "postgres://" (não só
        # "postgresql://") — em ambos os casos o SQLAlchemy interpreta como
        # psycopg2 por padrão, mas usamos psycopg3 (ver requirements.txt). Sem
        # isso, tanto a API quanto as migrations do Alembic falham ao conectar.
        if v is None:
            return v
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    jwt_secret_key: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ID do OAuth Client (tipo "Web application") criado no Google Cloud Console.
    # Usado tanto pelo frontend (botão "Entrar com Google") quanto pelo backend
    # (validar que o token recebido foi mesmo emitido pra este app). Ver security-access skill.
    google_oauth_client_id: str | None = None

    backend_cors_origins: list[str] = ["http://localhost:3000"]

    data_source_mode: str = "portal_rpa"  # "api_corban" | "portal_rpa"

    c6_api_corban_base_url: str | None = None
    c6_api_corban_client_id: str | None = None
    c6_api_corban_client_secret: str | None = None

    c6_portal_base_url: str = (
        "https://c6.c6consig.com.br/WebAutorizador/Login/AC.UI.LOGIN.aspx"
    )
    # A partir de out/26 a informação do negócio foi dividida em 2 acessos
    # Looker diferentes (parceiros "002921" e "003881") — cada login só
    # enxerga a fatia dele, e as duas precisam ser baixadas e empilhadas pra
    # ter o dado completo (ver `ContaLooker`/`_contas_looker()` em
    # `portal_rpa.py` e a orquestração em `atualizar_excel.py`). Pedido do
    # usuário em 2026-10-13.
    c6_portal_username_002921: str | None = None
    c6_portal_password_002921: str | None = None
    c6_portal_username_003881: str | None = None
    c6_portal_password_003881: str | None = None
    c6_portal_totp_secret: str | None = None

    pipeline_cron_schedules: str = "08:00,13:00,18:00"
    pipeline_timezone: str = "America/Sao_Paulo"

    # E-mail do primeiro admin, usado só pelo script de seed pra criar o registro
    # inicial em `users` — sem esse registro, ninguém consegue logar (nem o próprio
    # dono), já que login exige que o e-mail já exista cadastrado. Ver security-access skill.
    admin_email: str | None = None

    @property
    def pipeline_schedule_list(self) -> list[str]:
        return [s.strip() for s in self.pipeline_cron_schedules.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
