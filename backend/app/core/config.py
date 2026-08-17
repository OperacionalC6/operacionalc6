from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    backend_cors_origins: list[str] = ["http://localhost:3000"]

    data_source_mode: str = "portal_rpa"  # "api_corban" | "portal_rpa"

    c6_api_corban_base_url: str | None = None
    c6_api_corban_client_id: str | None = None
    c6_api_corban_client_secret: str | None = None

    c6_portal_base_url: str = (
        "https://c6.c6consig.com.br/WebAutorizador/Login/AC.UI.LOGIN.aspx"
    )
    c6_portal_username: str | None = None
    c6_portal_password: str | None = None
    c6_portal_totp_secret: str | None = None

    pipeline_cron_schedules: str = "08:00,13:00,18:00"
    pipeline_timezone: str = "America/Sao_Paulo"

    # Usado apenas pelo script de seed para criar o primeiro usuário admin.
    admin_email: str | None = None
    admin_password: str | None = None

    @property
    def pipeline_schedule_list(self) -> list[str]:
        return [s.strip() for s in self.pipeline_cron_schedules.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
