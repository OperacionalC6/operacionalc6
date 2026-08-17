"""
Conector para a API Corban oficial do C6 (canal preferencial e mais seguro
de integração — ver docs/API_CORBAN.md sobre como solicitar homologação).

Este módulo é um STUB estrutural: a Anthropic/este assistente não tem acesso
à documentação técnica oficial (endpoints, payloads, fluxo de autenticação)
da API Corban do C6, então os detalhes abaixo são placeholders. Depois que o
time obtiver a documentação de homologação junto ao C6, preencha:

  1. `_TOKEN_URL` e `_REPORTS_URL` com os endpoints reais fornecidos pelo C6.
  2. O fluxo de autenticação em `_authenticate` (client_credentials é o mais
     comum em APIs bancárias, mas confirme com a documentação).
  3. O mapeamento de campos em `_to_connector_records` de acordo com o
     schema real de resposta da API.

Até lá, `DATA_SOURCE_MODE=api_corban` levantará `NotImplementedError` de
forma explícita em vez de falhar silenciosamente ou inventar dados.
"""

from datetime import date, datetime, timedelta

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.services.connectors.base import ConnectorRecord, DataConnector

settings = get_settings()

# TODO: substituir pelos endpoints reais da documentação de homologação da API Corban.
_TOKEN_URL = "{base_url}/oauth/token"
_REPORTS_URL = "{base_url}/v1/relatorios/producao"


class ApiCorbanConnector(DataConnector):
    source_name = "api_corban"

    def __init__(self) -> None:
        if not (
            settings.c6_api_corban_base_url
            and settings.c6_api_corban_client_id
            and settings.c6_api_corban_client_secret
        ):
            raise RuntimeError(
                "API Corban não configurada. Defina C6_API_CORBAN_BASE_URL, "
                "C6_API_CORBAN_CLIENT_ID e C6_API_CORBAN_CLIENT_SECRET no .env "
                "após concluir a homologação (docs/API_CORBAN.md)."
            )
        self._base_url = settings.c6_api_corban_base_url.rstrip("/")
        self._client = httpx.Client(timeout=30.0)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
    def _authenticate(self) -> str:
        response = self._client.post(
            _TOKEN_URL.format(base_url=self._base_url),
            data={
                "grant_type": "client_credentials",
                "client_id": settings.c6_api_corban_client_id,
                "client_secret": settings.c6_api_corban_client_secret,
            },
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def fetch(self, *, date_from: date, date_to: date) -> list[ConnectorRecord]:
        raise NotImplementedError(
            "ApiCorbanConnector é um stub: implemente a chamada real à API Corban "
            "assim que a documentação de homologação do C6 estiver disponível. "
            "Enquanto isso, use DATA_SOURCE_MODE=portal_rpa."
        )

        # Esqueleto de referência (ajustar após ter a documentação real):
        #
        # token = self._authenticate()
        # response = self._client.get(
        #     _REPORTS_URL.format(base_url=self._base_url),
        #     headers={"Authorization": f"Bearer {token}"},
        #     params={"data_inicio": date_from.isoformat(), "data_fim": date_to.isoformat()},
        # )
        # response.raise_for_status()
        # return self._to_connector_records(response.json())

    @staticmethod
    def _to_connector_records(payload: dict) -> list[ConnectorRecord]:
        # TODO: mapear os campos reais retornados pela API para ConnectorRecord.
        raise NotImplementedError
