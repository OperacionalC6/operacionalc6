"""
Conector RPA (automação de portal web) para o WebAutorizador do C6 Consig e,
a partir da mesma sessão logada, para os dashboards Looker de comissão do
hub interno "One Page - Auto" (c6bank.cloud.looker.com).

*** LEIA ANTES DE USAR EM PRODUÇÃO ***

Automatizar login e extração de dados de um portal web bancário é uma
solução de fallback, não a solução preferida — ver docs/API_CORBAN.md para o
caminho recomendado (API oficial homologada). Antes de rodar isto contra o
portal real:

  1. Confirme com seu gestor de conta C6 / contrato de correspondente que a
     automação de acesso ao WebAutorizador é permitida. Muitos bancos proíbem
     scraping automatizado nos termos de uso de correspondentes bancários —
     violar isso pode levar a bloqueio de acesso ou penalidades contratuais.
  2. Use um usuário de automação dedicado (não uma conta pessoal de um
     analista), solicitado formalmente ao C6, para que o acesso possa ser
     auditado e revogado independentemente de contas de pessoas.
  3. Nunca commit credenciais — elas vêm de variáveis de ambiente/secrets
     manager (ver .env.example).
  4. Respeite o intervalo mínimo entre execuções (padrão: 2-3x/dia). Não
     reduza para evitar sobrecarregar/acionar defesas antifraude do portal.
  5. Os seletores em `portal_selectors.json` são placeholders — preencha com
     os seletores reais do portal (ver o _readme dentro do próprio arquivo)
     antes do primeiro uso.

Este conector roda em modo headless via Playwright (sync API), pensado para
ser executado dentro de um job do agendador (app/services/scheduler.py), não
durante uma requisição HTTP.
"""

import json
import logging
import os
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import pyotp
from playwright.sync_api import Page, sync_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.services.connectors.base import ConnectorRecord, DataConnector

logger = logging.getLogger(__name__)
settings = get_settings()

_CONFIG_PATH = Path(__file__).parent / "portal_selectors.json"
_ARTIFACTS_DIR = Path(os.environ.get("RPA_ARTIFACTS_DIR", "/app/artifacts"))
_HEADLESS = os.environ.get("HEADLESS", "true").lower() != "false"


class PortalLoginError(RuntimeError):
    pass


class PortalRpaConnector(DataConnector):
    source_name = "portal_rpa"

    def __init__(self) -> None:
        if not (settings.c6_portal_username and settings.c6_portal_password):
            raise RuntimeError(
                "Credenciais do portal não configuradas. Defina C6_PORTAL_USERNAME "
                "e C6_PORTAL_PASSWORD no .env (usuário de automação dedicado)."
            )
        self._config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    def fetch(self, *, date_from: date, date_to: date) -> list[ConnectorRecord]:
        records: list[ConnectorRecord] = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=_HEADLESS)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            try:
                self._login(page)
                for report_cfg in self._config["reports"]:
                    downloaded_file = self._download_report(page, report_cfg)
                    records.extend(
                        self._parse_report(downloaded_file, report_cfg, date_from, date_to)
                    )
                for looker_report_cfg in self._config.get("looker", {}).get("reports", []):
                    for downloaded_file, tile_cfg in self._download_looker_tiles(
                        page, looker_report_cfg
                    ):
                        if not tile_cfg.get("column_mapping"):
                            logger.info(
                                "Tile '%s' baixada em %s mas sem column_mapping "
                                "definido ainda — pulando parsing (arquivo fica "
                                "salvo para mapear depois).",
                                tile_cfg["name"],
                                downloaded_file,
                            )
                            continue
                        records.extend(
                            self._parse_report(downloaded_file, tile_cfg, date_from, date_to)
                        )
            except Exception:
                self._save_failure_artifacts(page)
                raise
            finally:
                context.close()
                browser.close()

        return records

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=3, max=15))
    def _login(self, page: Page) -> None:
        """
        O login do WebAutorizador é um postback assíncrono (UpdatePanel ASP.NET):
        ao clicar em "Entrar", a página pode (a) navegar para a área logada em
        caso de sucesso, ou (b) permanecer na mesma URL e exibir uma mensagem
        de erro em `#lblErro`/`#Sumario` em caso de falha — sem recarregar.
        Por isso não dá pra usar só `wait_for_navigation`; fazemos polling de
        três condições: menu pós-login apareceu (sucesso), mensagem de erro
        apareceu (falha), ou a URL saiu da tela de login (sucesso, fallback
        caso o seletor do menu mude no futuro).
        """
        login_cfg = self._config["login"]
        login_url_marker = login_cfg.get("login_url_marker", "AC.UI.LOGIN")
        error_selector = login_cfg.get("error_message_selector")
        success_selector = login_cfg.get("success_indicator_selector")

        page.goto(settings.c6_portal_base_url, wait_until="networkidle")

        page.fill(login_cfg["username_selector"], settings.c6_portal_username)
        page.fill(login_cfg["password_selector"], settings.c6_portal_password)

        if login_cfg.get("totp_selector") and settings.c6_portal_totp_secret:
            code = pyotp.TOTP(settings.c6_portal_totp_secret).now()
            page.fill(login_cfg["totp_selector"], code)

        page.click(login_cfg["submit_selector"])

        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if success_selector and page.locator(success_selector).first.count() > 0:
                logger.info("Login RPA no portal C6 concluído com sucesso (menu detectado).")
                return

            if login_url_marker not in page.url:
                logger.info("Login RPA no portal C6 concluído com sucesso (URL mudou).")
                return

            if error_selector:
                error_locator = page.locator(error_selector).first
                if error_locator.count() > 0:
                    error_text = error_locator.inner_text().strip()
                    if error_text:
                        raise PortalLoginError(
                            f"Falha ao autenticar no portal C6 (usuário de automação). "
                            f"Mensagem do portal: {error_text}."
                        )

            page.wait_for_timeout(500)

        raise PortalLoginError(
            "Timeout aguardando resposta do login no portal C6 — nem sucesso "
            "(mudança de URL) nem mensagem de erro foram detectados em 20s. "
            "O portal pode ter mudado; revise portal_selectors.json."
        )

    def _download_report(self, page: Page, report_cfg: dict) -> Path:
        base = settings.c6_portal_base_url.split("/WebAutorizador")[0]
        page.goto(f"{base}{report_cfg['path']}", wait_until="networkidle")

        with page.expect_download(timeout=report_cfg.get("download_wait_ms", 15000)) as download_info:
            page.click(report_cfg["export_button_selector"])
        download = download_info.value

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = _ARTIFACTS_DIR / f"{report_cfg['name']}_{timestamp}{Path(download.suggested_filename).suffix}"
        download.save_as(dest)
        logger.info("Relatório '%s' baixado em %s", report_cfg["name"], dest)
        return dest

    def _download_looker_tiles(
        self, page: Page, report_cfg: dict
    ) -> list[tuple[Path, dict]]:
        """
        Dashboards Looker (ex.: Apuração Parceiro 2.0) são um sistema à parte do
        WebAutorizador, em outro domínio (c6bank.cloud.looker.com), mas a mesma
        sessão de login já dá acesso — não é preciso autenticar de novo.

        Cada dashboard tem várias tiles (tabelas) que precisam ser baixadas
        separadamente, cada uma com seu próprio botão "Tile actions" — usamos o
        aria-label (estável) em vez das classes CSS com hash do Looker, que mudam
        a cada deploy.

        O filtro de período é aplicado via query string na própria URL do
        dashboard, em vez de manipular o seletor de datas na UI (mais frágil).
        PENDENTE VALIDAR com HEADLESS=false: se `filter_value` realmente produz
        o mesmo resultado que selecionar o mês corrente manualmente, e se
        "Download data" baixa direto ou abre um modal de confirmação/formato
        (ver `_atencao` em portal_selectors.json).
        """
        looker_cfg = self._config["looker"]
        url = f"{looker_cfg['base_url']}/embed/dashboards/{report_cfg['dashboard_slug']}"
        if report_cfg.get("filter_param") and report_cfg.get("filter_value"):
            url += (
                f"?{quote(report_cfg['filter_param'])}="
                f"{quote(report_cfg['filter_value'])}"
            )

        page.goto(url, wait_until="networkidle")

        download_menu_item = looker_cfg.get("download_menu_item_text", "Download data")
        results: list[tuple[Path, dict]] = []
        for tile in report_cfg["tiles"]:
            with page.expect_download(
                timeout=report_cfg.get("download_wait_ms", 20000)
            ) as download_info:
                page.get_by_role("button", name=f"{tile['name']} - Tile actions").click()
                page.get_by_text(download_menu_item, exact=True).click()
            download = download_info.value

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = (
                _ARTIFACTS_DIR
                / f"{report_cfg['name']}_{tile['key']}_{timestamp}"
                f"{Path(download.suggested_filename).suffix}"
            )
            download.save_as(dest)
            logger.info(
                "Tile '%s' do relatório Looker '%s' baixado em %s",
                tile["name"],
                report_cfg["name"],
                dest,
            )
            results.append((dest, tile))
        return results

    @staticmethod
    def _parse_report(
        file_path: Path, report_cfg: dict, date_from: date, date_to: date
    ) -> list[ConnectorRecord]:
        mapping = report_cfg["column_mapping"]

        if file_path.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path, sep=None, engine="python")

        df[mapping["date_column"]] = pd.to_datetime(df[mapping["date_column"]]).dt.date
        df = df[(df[mapping["date_column"]] >= date_from) & (df[mapping["date_column"]] <= date_to)]

        records: list[ConnectorRecord] = []
        for _, row in df.iterrows():
            dimensions = {
                col: row[col] for col in mapping.get("dimension_columns", []) if col in df.columns
            }
            records.append(
                ConnectorRecord(
                    team_name=str(row[mapping["team_column"]]) if mapping.get("team_column") else None,
                    metric_date=row[mapping["date_column"]],
                    metric_name=mapping["metric_name"],
                    value=float(row[mapping["value_column"]]),
                    dimensions=dimensions or None,
                )
            )
        return records

    @staticmethod
    def _save_failure_artifacts(page: Page) -> None:
        """Salva screenshot/HTML da página no momento da falha, para debug — nunca loga credenciais."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            page.screenshot(path=str(_ARTIFACTS_DIR / f"failure_{timestamp}.png"), full_page=True)
            (_ARTIFACTS_DIR / f"failure_{timestamp}.html").write_text(page.content(), encoding="utf-8")
        except Exception:
            logger.exception("Não foi possível salvar artefatos de falha do RPA.")
