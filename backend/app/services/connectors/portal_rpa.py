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
_BROWSER_PROFILE_DIR = Path(os.environ.get("RPA_BROWSER_PROFILE_DIR", "/app/browser_profile"))


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
        _BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    def fetch(self, *, date_from: date, date_to: date) -> list[ConnectorRecord]:
        """
        Usa um perfil de navegador PERSISTENTE (salvo em RPA_BROWSER_PROFILE_DIR)
        em vez de um contexto novo/descartável a cada execução. Motivo: o
        WebAutorizador exibe uma verificação extra de dispositivo ("Acessar
        outros apps e serviços neste dispositivo") quando o login vem de um
        navegador "desconhecido" — o que um contexto novo do Playwright sempre
        parece ser, mesmo em uso legítimo. Um perfil persistente se comporta como
        o Chrome do dia a dia: uma vez que o dispositivo seja aprovado numa
        primeira rodada manual (HEADLESS=false), o cookie/estado de confiança
        fica salvo em disco e roda headless depois — sem tentar disfarçar a
        automação, só reaproveitando uma sessão já aprovada.
        """
        records: list[ConnectorRecord] = []

        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                str(_BROWSER_PROFILE_DIR),
                headless=_HEADLESS,
                accept_downloads=True,
                # Evita o popup nativo "Salvar senha?" do Chrome, que interrompe
                # a automação esperando alguém clicar "Nunca"/"Salvar".
                args=["--disable-save-password-bubble"],
            )
            page = context.pages[0] if context.pages else context.new_page()
            # Por padrão o Playwright fecha sozinho qualquer confirm()/alert()
            # nativo do navegador (como se clicasse "Cancelar"), sem executar o
            # código do script. O WebAutorizador usa um confirm() real pra
            # perguntar "Usuário já autenticado em outra estação, desconectar?"
            # quando sobra uma sessão anterior — sem isso, o login trava
            # esperando uma resposta que nunca chega. Aceitar equivale a
            # clicar "Sim" nesse popup, igual um humano faria.
            page.on("dialog", lambda dialog: dialog.accept())
            try:
                self._login(page)
                for report_cfg in self._config["reports"]:
                    if not report_cfg.get("export_button_selector"):
                        logger.info(
                            "Relatório '%s' ainda sem export_button_selector definido "
                            "— pulando (preencha portal_selectors.json quando tiver "
                            "o seletor real).",
                            report_cfg["name"],
                        )
                        continue
                    downloaded_file = self._download_report(page, report_cfg)
                    records.extend(
                        self._parse_report(downloaded_file, report_cfg, date_from, date_to)
                    )
                looker_reports = self._config.get("looker", {}).get("reports", [])
                if looker_reports:
                    self._bootstrap_looker_session(page)
                for looker_report_cfg in looker_reports:
                    for downloaded_file, tile_cfg in self._download_looker_tiles(
                        page, looker_report_cfg
                    ):
                        mapping_cfg = tile_cfg.get("column_mapping")
                        if not mapping_cfg:
                            logger.info(
                                "Tile '%s' baixada em %s mas sem column_mapping "
                                "definido ainda — pulando parsing (arquivo fica "
                                "salvo para mapear depois).",
                                tile_cfg["name"],
                                downloaded_file,
                            )
                            continue
                        # column_mapping pode ser um dict único (1 métrica) ou uma lista
                        # de dicts (várias métricas extraídas do MESMO arquivo baixado) —
                        # necessário porque uma tile do Looker pode trazer mais de um
                        # número que vale a pena virar métrica separada (ex.: tile
                        # "Comissão Total" traz À Vista E Carteira na mesma linha).
                        mappings = mapping_cfg if isinstance(mapping_cfg, list) else [mapping_cfg]
                        for mapping in mappings:
                            records.extend(
                                self._parse_report(
                                    downloaded_file, {"column_mapping": mapping}, date_from, date_to
                                )
                            )
            except Exception:
                self._save_failure_artifacts(page)
                raise
            finally:
                context.close()

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

        # "networkidle" trava em sites com scripts de antifraude que mantêm
        # chamadas de rede em segundo plano (ex.: checagem de dispositivo do
        # WebAutorizador) — a espera nunca "acalma" e o goto acaba estourando
        # timeout. Esperamos só o HTML carregar e depois o campo de usuário
        # aparecer, que é o que realmente importa para prosseguir.
        page.goto(settings.c6_portal_base_url, wait_until="domcontentloaded")
        page.locator(login_cfg["username_selector"]).wait_for(state="visible", timeout=20000)

        page.fill(login_cfg["username_selector"], settings.c6_portal_username)
        page.fill(login_cfg["password_selector"], settings.c6_portal_password)

        if login_cfg.get("totp_selector") and settings.c6_portal_totp_secret:
            code = pyotp.TOTP(settings.c6_portal_totp_secret).now()
            page.fill(login_cfg["totp_selector"], code)

        page.click(login_cfg["submit_selector"])

        deadline = time.monotonic() + 60
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
            "(mudança de URL) nem mensagem de erro foram detectados em 60s. "
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

    def _bootstrap_looker_session(self, page: Page) -> None:
        """
        Ir direto pra URL de um dashboard Looker sem passar por essa página do
        WebAutorizador antes resulta em "não autorizado" (confirmado em teste
        real) — essa página faz algum handshake/SSO com o Looker que autoriza
        a sessão do navegador a acessar os dashboards depois. No uso manual,
        isso acontece ao clicar em Relatórios > Relatórios Gerenciais.
        """
        looker_cfg = self._config["looker"]
        base = settings.c6_portal_base_url.split("/WebAutorizador")[0]
        page.goto(f"{base}{looker_cfg['bootstrap_path']}", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

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
        if report_cfg.get("filter_query"):
            # Query string completa, já codificada, copiada direto da URL real do
            # dashboard (usada quando o relatório tem muitos filtros — mais simples
            # e mais fiel colar a URL toda do que tentar reconstruir cada parâmetro).
            # {current_month} é substituído pelo mês corrente (AAAA-MM) — necessário
            # pra filtros de "mês de referência" fixo (não são uma janela relativa
            # tipo "6 month"/"30 day" que o próprio Looker já rola sozinho).
            filter_query = report_cfg["filter_query"].replace(
                "{current_month}", datetime.now().strftime("%Y-%m")
            )
            url += f"?{filter_query}"
        elif report_cfg.get("filter_param") and report_cfg.get("filter_value"):
            url += (
                f"?{quote(report_cfg['filter_param'])}="
                f"{quote(report_cfg['filter_value'])}"
            )

        # Mesmo motivo do login: "networkidle" trava em dashboards Looker, que
        # mantêm chamadas de rede o tempo todo (polling, analytics). Esperamos
        # o botão "Tile actions" da primeira tile aparecer, que é sinal de que
        # o dashboard renderizou de verdade.
        page.goto(url, wait_until="domcontentloaded")
        first_tile_name = report_cfg["tiles"][0]["name"]
        page.get_by_role("button", name=f"{first_tile_name} - Tile actions").wait_for(
            state="visible", timeout=30000
        )

        download_menu_item = looker_cfg.get("download_menu_item_text", "Download data")
        results: list[tuple[Path, dict]] = []
        for tile in report_cfg["tiles"]:
            with page.expect_download(
                timeout=report_cfg.get("download_wait_ms", 20000)
            ) as download_info:
                page.get_by_role("button", name=f"{tile['name']} - Tile actions").click()
                page.get_by_text(download_menu_item, exact=True).click()
                # "Download data" abre um modal (formato do arquivo, já vem CSV
                # selecionado por padrão) em vez de baixar direto — confirmado
                # em teste real. Falta confirmar clicando no botão "Download"
                # do modal.
                page.get_by_role("button", name="Download", exact=True).click()
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
    def _parse_brl_value(raw: object) -> float:
        """
        Colunas monetárias dos exports Looker vêm formatadas como texto, ex.:
        'R$ 653,440.00' (vírgula de milhar, ponto decimal — não é o formato
        BR tradicional, é o locale do Looker). Remove o prefixo e a vírgula
        antes de converter.
        """
        if isinstance(raw, (int, float)):
            return float(raw)
        cleaned = str(raw).replace("R$", "").replace(",", "").strip()
        return float(cleaned)

    @staticmethod
    def _parse_report(
        file_path: Path, report_cfg: dict, date_from: date, date_to: date
    ) -> list[ConnectorRecord]:
        mapping = report_cfg["column_mapping"]

        if file_path.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        else:
            # Sem sep=None/engine="python": os exports do Looker têm valores
            # monetários entre aspas com vírgula de milhar dentro (ex.: "R$
            # 653,440.00") — o sniffer de separador do engine python se
            # confunde com isso. O parser padrão (C) já lida bem com aspas.
            df = pd.read_csv(file_path)

        date_format = mapping.get("date_format")
        df[mapping["date_column"]] = pd.to_datetime(
            df[mapping["date_column"]], format=date_format
        ).dt.date
        df = df[(df[mapping["date_column"]] >= date_from) & (df[mapping["date_column"]] <= date_to)]

        records: list[ConnectorRecord] = []
        for _, row in df.iterrows():
            # pd.isna() em vez de checar direto: células vazias no CSV do Looker viram
            # NaN (float) do pandas, e o serializador de JSON do Postgres rejeita o
            # token "NaN" (não é JSON válido, mesmo o json do Python aceitando por
            # padrão) — quebra o INSERT inteiro do lote por causa de uma linha só.
            # Convertemos pra None (vira null no JSON) em vez de perder a linha.
            dimensions = {
                col: (None if pd.isna(row[col]) else row[col])
                for col in mapping.get("dimension_columns", [])
                if col in df.columns
            }
            value = PortalRpaConnector._parse_brl_value(row[mapping["value_column"]])
            if pd.isna(value):
                # Célula de valor vazia (ex.: mês corrente ainda sem apuração/estimativa
                # calculada) — diferente de dimensão NaN (vira None/null), aqui não tem
                # como gravar 'NaN' numa métrica sem quebrar soma/média futura em SQL.
                # Pular a linha é melhor que gravar um valor inválido.
                continue
            records.append(
                ConnectorRecord(
                    team_name=str(row[mapping["team_column"]]) if mapping.get("team_column") else None,
                    metric_date=row[mapping["date_column"]],
                    metric_name=mapping["metric_name"],
                    value=value,
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


def _run_cli() -> None:
    """
    Execução manual para validar o RPA visualmente contra o portal real antes de
    colocar em produção. Rode com HEADLESS=false para ver o navegador:

        HEADLESS=false RPA_ARTIFACTS_DIR=./artifacts RPA_BROWSER_PROFILE_DIR=./browser_profile \\
            python -m app.services.connectors.portal_rpa --debug

    Na PRIMEIRA vez, se o portal pedir a verificação de dispositivo, resolva
    manualmente (clique em Permitir/Bloquear) — como o perfil agora é
    persistente (salvo em RPA_BROWSER_PROFILE_DIR), essa aprovação fica salva
    e runs futuras (inclusive headless, num servidor) devem reaproveitar o
    mesmo "dispositivo" sem pedir de novo.

    Credenciais vêm do .env (C6_PORTAL_USERNAME / C6_PORTAL_PASSWORD) — nunca
    passe usuário/senha por linha de comando ou variável exposta em logs.
    Nunca commite a pasta de RPA_BROWSER_PROFILE_DIR — ela guarda cookies de
    sessão reais.
    """
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug", action="store_true", help="Logs em nível DEBUG.")
    parser.add_argument(
        "--date-from",
        type=date.fromisoformat,
        default=date.today().replace(day=1),
        help="Data inicial YYYY-MM-DD (padrão: dia 1 do mês corrente).",
    )
    parser.add_argument(
        "--date-to",
        type=date.fromisoformat,
        default=date.today(),
        help="Data final YYYY-MM-DD (padrão: hoje).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    connector = PortalRpaConnector()
    records = connector.fetch(date_from=args.date_from, date_to=args.date_to)

    logger.info("Total de registros extraídos e parseados: %d", len(records))
    for record in records[:10]:
        logger.info(record)
    logger.info(
        "Arquivos baixados (inclusive tiles sem column_mapping ainda) ficam em: %s",
        _ARTIFACTS_DIR,
    )


if __name__ == "__main__":
    _run_cli()
