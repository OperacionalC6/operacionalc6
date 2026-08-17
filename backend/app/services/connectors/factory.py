from app.core.config import get_settings
from app.services.connectors.base import DataConnector


def get_connector() -> DataConnector:
    settings = get_settings()

    if settings.data_source_mode == "api_corban":
        from app.services.connectors.api_corban import ApiCorbanConnector

        return ApiCorbanConnector()

    if settings.data_source_mode == "portal_rpa":
        from app.services.connectors.portal_rpa import PortalRpaConnector

        return PortalRpaConnector()

    raise ValueError(
        f"DATA_SOURCE_MODE inválido: '{settings.data_source_mode}'. "
        "Use 'api_corban' ou 'portal_rpa'."
    )
