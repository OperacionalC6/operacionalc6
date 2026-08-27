"""
Script de inicialização: garante que exista ao menos um usuário admin.
Idempotente — pode ser executado a cada start do container sem duplicar dados.

Sem esse registro, NINGUÉM consegue logar — login exige que o e-mail já exista
cadastrado em `users` com is_active=True (não há senha nem cadastro público, ver
security-access skill). Defina ADMIN_EMAIL no ambiente com o Gmail de quem vai
administrar o sistema antes do primeiro start.

Executar com: python -m app.seed
"""

import logging

from app.core.config import get_settings
from app.core.logging import configure_logging
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

        if not settings.admin_email:
            logger.warning(
                "ADMIN_EMAIL não definido — nenhum usuário admin foi criado. "
                "Ninguém conseguirá logar até definir ADMIN_EMAIL e rodar o seed de novo."
            )
            return

        admin = User(
            email=settings.admin_email.lower(),
            full_name="Administrador",
            role=UserRole.ADMIN,
        )
        db.add(admin)
        db.commit()

        logger.info("Usuário admin criado: %s — já pode logar com 'Entrar com Google'.", admin.email)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
