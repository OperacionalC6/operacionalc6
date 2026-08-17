"""
Script de inicialização: garante que exista ao menos um usuário admin.
Idempotente — pode ser executado a cada start do container sem duplicar dados.

Executar com: python -m app.seed
"""

import logging
import secrets

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole

configure_logging()
logger = logging.getLogger(__name__)


def seed() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            logger.info("Seed ignorado: já existem usuários cadastrados.")
            return

        admin_email = (settings.admin_email or "admin@suaempresa.com.br").lower()
        admin_password = settings.admin_password or secrets.token_urlsafe(16)

        admin = User(
            email=admin_email,
            full_name="Administrador",
            hashed_password=hash_password(admin_password),
            role=UserRole.ADMIN,
            must_change_password=True,
        )
        db.add(admin)
        db.commit()

        logger.warning(
            "Usuário admin criado: %s | senha inicial: %s "
            "— TROQUE a senha no primeiro login (ela não será exibida novamente).",
            admin_email,
            admin_password,
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed()
