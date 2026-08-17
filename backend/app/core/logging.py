import logging
import sys

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
    # Silencia logs verbosos de bibliotecas de terceiros em produção.
    if settings.environment != "development":
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
