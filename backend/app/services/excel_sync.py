"""
Sincroniza abas do `Construcao.xlsx` do usuário direto com o Looker, sem
passar pelo Postgres/app web (decisão de 2026-09-24, ver skill
`project-context` — a infra de nuvem foi desativada e o projeto virou uma
automação local em cima do próprio Excel do usuário).

Reaproveita o login/navegação/download do RPA já validado
(`PortalRpaConnector`), mas NÃO usa `_parse_report`/`ConnectorRecord` (que
filtra só as `dimension_columns` configuradas pro app web) — aqui precisamos
de TODAS as colunas brutas do export, porque é exatamente isso que já está
na planilha do usuário (inclusive colunas de PII como Cpf/Nm Cliente que o
app web deliberadamente não guardava).

Descoberta real inspecionando a planilha (2026-09-24): as abas `db_pagasanalitico`
e `db_mercado` têm colunas DERIVADAS (fórmula) antes das colunas brutas do
Looker (ex.: `db_pagasanalitico` tem 12 colunas de fórmula A:L antes da coluna
bruta M "ID Proposta"). Ao inserir linha nova, essas fórmulas são "arrastadas"
pra baixo com `openpyxl.formula.translate.Translator` — o mesmo mecanismo que
o Excel usa internamente quando você arrasta a alcinha de preenchimento
(ajusta referência relativa de linha, preserva coluna absoluta e referência
de coluna inteira). Testado contra os padrões reais de fórmula da planilha
antes de usar em produção.

Duas restrições de segurança, as duas por causa de como o `openpyxl` mexe em
linha (NÃO reescreve texto de fórmula ao inserir/apagar linha no meio de uma
aba — diferente do Excel de verdade, que ajusta fórmulas automaticamente):

1. Toda atualização (`atualizar_*`) só mexe no BLOCO FINAL (mais recente) de
   cada aba — nunca no meio. Se o dia/mês pedido não for encontrado colado no
   final dos dados já existentes, a função recusa e não altera nada. Isso
   evita corromper silenciosamente milhares de fórmulas auto-referenciadas
   abaixo de um ponto de inserção no meio da aba.
2. `base_final` tem uma dependência a mais: ela referencia `db_apuracaoavista`
   por POSIÇÃO de linha (não por XLOOKUP) — então só é seguro atualizar
   `db_apuracaoavista` se o mês pedido for o ÚLTIMO bloco da aba (senão todo
   o resto do `base_final` calculado depois daquele ponto ficaria deslocado).
   `db_pagasanalitico`/`db_mercado` não têm esse problema (o `base_final`
   busca neles por XLOOKUP em coluna inteira, que não liga pra posição).
"""

import logging
import re
from contextlib import contextmanager
from copy import copy
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from openpyxl.formula.translate import Translator
from openpyxl.worksheet.worksheet import Worksheet
from playwright.sync_api import Page, sync_playwright

from app.services.connectors.portal_rpa import (
    _ARTIFACTS_DIR,
    _BROWSER_PROFILE_DIR,
    _HEADLESS,
    PortalRpaConnector,
    _accept_dialog_logged,
)

logger = logging.getLogger(__name__)

_EVIDENCIAS_DIR = _ARTIFACTS_DIR / "evidencias"


class AtualizacaoRecusada(RuntimeError):
    """Levantada quando a atualização pedida não é segura de aplicar (ver
    docstring do módulo — nunca mexer no meio de uma aba com fórmula)."""


# ---------------------------------------------------------------------------
# Download (Looker -> DataFrame bruto, todas as colunas)
# ---------------------------------------------------------------------------


def _find_report_cfg(config: dict, report_name: str) -> dict:
    for report in config["looker"]["reports"]:
        if report["name"] == report_name:
            return report
    raise RuntimeError(f"Relatório '{report_name}' não encontrado em portal_selectors.json.")


def _find_tile_cfg(report_cfg: dict, tile_key: str) -> dict:
    for tile in report_cfg["tiles"]:
        if tile["key"] == tile_key:
            return tile
    raise RuntimeError(
        f"Tile '{tile_key}' não encontrada no relatório '{report_cfg['name']}'."
    )


@contextmanager
def sessao_looker():
    """Abre UMA sessão autenticada no portal (login + bootstrap do Looker) e
    entrega `(connector, page)` pra quem quiser baixar VÁRIAS tiles sem logar
    de novo a cada uma — passe o resultado pro parâmetro `sessao` de
    `baixar_looker_bruto`. Usado pelo `--tudo` do CLI: sem isso, atualizar as
    3 abas de uma vez fazia 3 logins inteiros (um por download), quando dava
    pra fazer só 1."""
    connector = PortalRpaConnector()
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(_BROWSER_PROFILE_DIR),
            headless=_HEADLESS,
            accept_downloads=True,
            args=["--disable-save-password-bubble"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.on("dialog", _accept_dialog_logged)
        try:
            connector._login(page)
            connector._bootstrap_looker_session(page)
            yield connector, page
        except Exception:
            connector._save_failure_artifacts(page)
            raise
        finally:
            context.close()


def _tirar_print_evidencia(page: Page, report_name: str) -> Path:
    """Print de tela do dashboard Looker logo depois do filtro aplicado e
    renderizado (mesmo estado que gerou os dados baixados) — serve de
    evidência visual pro relatório de atualização, pra conferir que o número
    baixado bate com o que o Looker mostra na tela."""
    _EVIDENCIAS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = _EVIDENCIAS_DIR / f"{report_name}_{timestamp}.png"
    page.screenshot(path=str(dest), full_page=True)
    return dest


def baixar_looker_bruto(
    report_name: str,
    tile_key: str,
    *,
    filter_query_override: str | None = None,
    filter_value_override: str | None = None,
    sessao: tuple[PortalRpaConnector, Page] | None = None,
    evidencias: list[Path] | None = None,
) -> pd.DataFrame:
    """
    Baixa UMA tile de UM relatório Looker e devolve o DataFrame bruto (todas
    as colunas do export, sem filtrar nada). Reaproveita o login/bootstrap/
    download já validados em `PortalRpaConnector` — só troca o que acontece
    DEPOIS do download (lá vira `ConnectorRecord` filtrado; aqui fica o
    DataFrame inteiro).

    `filter_query_override`/`filter_value_override`: sobrescreve o filtro de
    período configurado em `portal_selectors.json` (que é relativo, tipo
    "3 day"/"2 months") por um filtro de dia/mês EXATO — necessário porque
    aqui pedimos um dia ou mês específico, não "os últimos N".

    `sessao`: passa `(connector, page)` já logados (ver `sessao_looker`) pra
    reaproveitar a mesma sessão entre vários downloads numa única execução —
    se omitido (uso normal, 1 aba isolada), abre e fecha uma sessão só pra
    esse download.

    `evidencias`: lista mutável — se passada, um print da tela do dashboard
    (ver `_tirar_print_evidencia`) é tirado logo após o download e o caminho
    do arquivo é adicionado nela (usado pra montar o relatório final).
    """
    conector_para_config = sessao[0] if sessao is not None else PortalRpaConnector()
    report_cfg = dict(_find_report_cfg(conector_para_config._config, report_name))
    tile_cfg = _find_tile_cfg(report_cfg, tile_key)
    report_cfg["tiles"] = [tile_cfg]  # baixa só a tile pedida, não as outras do mesmo relatório

    if filter_query_override is not None:
        report_cfg["filter_query"] = filter_query_override
        report_cfg.pop("filter_param", None)
        report_cfg.pop("filter_value", None)
    elif filter_value_override is not None:
        report_cfg["filter_value"] = filter_value_override

    if sessao is not None:
        connector, page = sessao
        downloaded = connector._download_looker_tiles(page, report_cfg)
        if evidencias is not None:
            evidencias.append(_tirar_print_evidencia(page, report_name))
    else:
        with sessao_looker() as (connector, page):
            downloaded = connector._download_looker_tiles(page, report_cfg)
            if evidencias is not None:
                evidencias.append(_tirar_print_evidencia(page, report_name))

    file_path, _tile = downloaded[0]
    if file_path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(file_path)
    else:
        df = pd.read_csv(file_path)
    logger.info(
        "Baixado '%s'/'%s': %d linhas, %d colunas (arquivo: %s).",
        report_name,
        tile_key,
        len(df),
        len(df.columns),
        file_path,
    )
    return df


# ---------------------------------------------------------------------------
# Leitura/escrita de planilha (genérico, usado pelas 3 abas)
# ---------------------------------------------------------------------------


def _header_map(ws: Worksheet, header_row: int) -> dict[str, int]:
    """Nome de coluna (linha de cabeçalho) -> índice de coluna (1-based)."""
    mapa: dict[str, int] = {}
    for cell in ws[header_row]:
        if cell.value:
            mapa[str(cell.value).strip()] = cell.column
    return mapa


def _colunas_formula(ws: Worksheet, linha_modelo: int, max_col: int) -> list[int]:
    """Colunas onde a linha-modelo tem FÓRMULA (começa com '=') — são as
    colunas derivadas que precisam ser arrastadas pra linha nova. As demais
    são colunas de dado bruto, onde escrevemos o valor baixado do Looker."""
    cols = []
    for col in range(1, max_col + 1):
        v = ws.cell(row=linha_modelo, column=col).value
        if isinstance(v, str) and v.startswith("="):
            cols.append(col)
    return cols


def _copiar_estilo(ws: Worksheet, linha_modelo: int, linha_destino: int, col: int) -> None:
    """Copia o ESTILO completo da célula-modelo pra célula nova: number_format
    (moeda/%/data/etc.), fonte, cor de fundo, borda e alinhamento. Sem isso,
    célula nova criada além do `max_row` anterior nasce com o estilo padrão
    "General"/sem formatação nenhuma — mesmo com o VALOR certo (achado real em
    2026-09-24: o código não copiava estilo nenhum, nem aqui nem em
    `_escrever_linhas_brutas`; a 1ª correção só copiou number_format, mas
    fonte/cor/borda/alinhamento ainda ficavam default). Precisa de `copy.copy()`
    em cada objeto de estilo — `cell.font` etc. devolvem um proxy vinculado à
    célula de origem, e o openpyxl recusa (`TypeError: unhashable type:
    'StyleProxy'`) se a mesma instância for atribuída direto a outra célula."""
    origem = ws.cell(row=linha_modelo, column=col)
    destino = ws.cell(row=linha_destino, column=col)
    destino.number_format = origem.number_format
    destino.font = copy(origem.font)
    destino.fill = copy(origem.fill)
    destino.border = copy(origem.border)
    destino.alignment = copy(origem.alignment)
    destino.protection = copy(origem.protection)


def _arrastar_linha(
    ws: Worksheet, linha_modelo: int, linha_destino: int, colunas_formula: list[int]
) -> None:
    """Copia as fórmulas de `linha_modelo` pra `linha_destino` nas colunas
    dadas, via `Translator` (ver docstring do módulo)."""
    for col in colunas_formula:
        origem_coord = ws.cell(row=linha_modelo, column=col).coordinate
        destino_coord = ws.cell(row=linha_destino, column=col).coordinate
        formula = ws.cell(row=linha_modelo, column=col).value
        ws.cell(row=linha_destino, column=col).value = Translator(
            formula, origin=origem_coord
        ).translate_formula(destino_coord)
        _copiar_estilo(ws, linha_modelo, linha_destino, col)


def _ultima_linha_com_dado(ws: Worksheet, col_chave: int, header_row: int) -> int:
    """Última linha (de baixo pra cima) com valor não vazio na coluna-chave
    dada. Devolve `header_row` se a aba não tiver nenhuma linha de dado."""
    for r in range(ws.max_row, header_row, -1):
        if ws.cell(row=r, column=col_chave).value not in (None, ""):
            return r
    return header_row


def _bloco_final_que_bate(
    ws: Worksheet,
    header_row: int,
    ultima_linha: int,
    col_chave: int,
    bate: "callable[[object], bool]",
) -> tuple[int, int] | None:
    """
    Acha o bloco CONTÍGUO de linhas, colado no final dos dados já existentes,
    cujo valor na coluna-chave satisfaz `bate` — ex.: "Dt Relatório" == um dia
    específico, ou "Anomes Apuracao" == um mês específico.

    Devolve (primeira_linha, ultima_linha) do bloco, ou `None` se a última
    linha de dado já não bater (ou seja: o dia/mês pedido não é o mais
    recente da aba — quem chama decide o que fazer, normalmente recusar).
    """
    if ultima_linha <= header_row:
        return None
    if not bate(ws.cell(row=ultima_linha, column=col_chave).value):
        return None
    primeira = ultima_linha
    while primeira > header_row and bate(ws.cell(row=primeira - 1, column=col_chave).value):
        primeira -= 1
    return primeira, ultima_linha


_RE_VALOR_MONETARIO = re.compile(r"^-?R\$\s*[\d.,]+$")


def _normalizar_valor_bruto(valor: object) -> object:
    """Converte string monetária do Looker (ex.: "R$ 1,506.47") pro float
    correspondente — usa o mesmo `parse_looker_number` já usado no resto do
    código (ver `_num`/`PortalRpaConnector._parse_brl_value`). Sem isso, essas
    colunas entravam como TEXTO puro nas linhas novas, diferente das linhas
    antigas (sempre número de verdade), quebrando silenciosamente qualquer
    fórmula que soma/compara essas células (achado real em 2026-09-24: colunas
    AO/AT viraram 'R$ 1,506.47' em vez de 1506.47 nas linhas inseridas hoje).
    Só mexe em valores que claramente parecem dinheiro no formato do Looker —
    texto genérico (nome, status, CNPJ, etc.) fica intocado."""
    if isinstance(valor, str) and _RE_VALOR_MONETARIO.match(valor.strip()):
        from app.services.connectors.base import parse_looker_number

        return parse_looker_number(valor)
    return valor


def _escrever_linhas_brutas(
    ws: Worksheet,
    linha_inicio: int,
    df: pd.DataFrame,
    mapa_colunas: dict[str, int],
    linha_modelo: int,
) -> None:
    """Escreve `df` a partir de `linha_inicio`, uma linha do Excel por linha
    do DataFrame, só nas colunas de dado bruto (mapeadas por nome — colunas
    do DataFrame sem correspondência no cabeçalho da aba são ignoradas).
    Normaliza valor monetário em texto pra número (ver `_normalizar_valor_bruto`)
    e copia o estilo completo (`_copiar_estilo`) da `linha_modelo` pra cada
    célula nova."""
    for offset, (_, row) in enumerate(df.iterrows()):
        linha_excel = linha_inicio + offset
        for nome_coluna, valor in row.items():
            col = mapa_colunas.get(str(nome_coluna).strip())
            if col is None:
                continue
            if pd.isna(valor):
                valor = None
            else:
                valor = _normalizar_valor_bruto(valor)
            ws.cell(row=linha_excel, column=col).value = valor
            _copiar_estilo(ws, linha_modelo, linha_excel, col)


def _as_date(v: object) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return None


# ---------------------------------------------------------------------------
# db_pagasanalitico (grão: dia) — acompanhamento_veiculos / analitico
# ---------------------------------------------------------------------------


def atualizar_db_pagasanalitico(
    wb,
    dia: date,
    *,
    sessao: tuple[PortalRpaConnector, Page] | None = None,
    evidencias: list[Path] | None = None,
) -> dict:
    ws = wb["db_pagasanalitico"]
    header_row = 1
    mapa = _header_map(ws, header_row)
    col_dt = mapa["Dt Relatório"]

    ultima = _ultima_linha_com_dado(ws, col_dt, header_row)
    if ultima > header_row:
        ultima_data = _as_date(ws.cell(row=ultima, column=col_dt).value)
        if ultima_data is not None and dia < ultima_data:
            raise AtualizacaoRecusada(
                f"O dia {dia.isoformat()} é anterior ao último dia já presente na aba "
                f"({ultima_data.isoformat()}) e não está colado no final dos dados — "
                "atualizar no meio da aba corromperia as fórmulas das linhas depois dele "
                "(ver docstring do módulo). Não vou mexer nada."
            )

    bloco = _bloco_final_que_bate(
        ws, header_row, ultima, col_dt, lambda v: _as_date(v) == dia
    )
    linha_modelo = ultima if ultima > header_row else None
    if bloco is not None:
        linha_modelo = bloco[0] - 1 if bloco[0] - 1 > header_row else linha_modelo

    if linha_modelo is None:
        raise AtualizacaoRecusada(
            "db_pagasanalitico está vazia (sem nenhuma linha de dado) — não há uma "
            "linha-modelo pra copiar as fórmulas das colunas derivadas. Preencha ao "
            "menos 1 linha manualmente no Excel antes de rodar a automação."
        )

    # Baixa ANTES de mexer na planilha — se o download falhar, nada foi
    # alterado no workbook em memória (e o CLI, por sua vez, não salva nada
    # no disco se uma exceção subir até ele).
    filtro = (
        "Tipo+Exibicao=qtde%5E_propostas&Tipo+Veiculo=&Tipo+Pessoa="
        f"&Dt+Relatorio+Date={dia.isoformat()}"
        "&Lojista=&Status+Proposta=&Fase=&GP=&SUPERVISOR=&GN=&Tipo+Cupom="
        "&Tp+Atendimento=CORBAN&Equipe+de+venda=&Grupo=&AUTOSHOPPING=&Shopping="
        "&Concessionaria=&Rede=&Rede+%2B+Regional=&Plataforma=&Filial="
        "&Classificacao+Loja=&UF+Loja=&Cidade+Loja=&Bairro+Loja=&A%C3%A7%C3%A3o+Loja="
        "&Onda+Lib+URL=&Quebra=&ID+Proposta=&CPF=&Idade+Do+Bem=&Rating+Cliente="
        "&S+Cliente=&Gerente+Coordenador+Meta=&Gerente+Neg%C3%B3cios+Meta="
        "&Gerente+Coordenador+Corban=&Gerente+Neg%C3%B3cios+Corban=&Cd+Loja="
    )
    df = baixar_looker_bruto(
        "acompanhamento_veiculos",
        "analitico",
        filter_query_override=filtro,
        sessao=sessao,
        evidencias=evidencias,
    )
    df["Dt Relatório"] = pd.to_datetime(df["Dt Relatório"]).dt.date
    df = df[df["Dt Relatório"] == dia].reset_index(drop=True)

    if bloco is not None:
        qtd_removida = bloco[1] - bloco[0] + 1
        ws.delete_rows(bloco[0], qtd_removida)
        linha_inicio = bloco[0]
        logger.info("db_pagasanalitico: removidas %d linhas antigas do dia %s antes de reinserir.", qtd_removida, dia)
    else:
        linha_inicio = ultima + 1

    colunas_formula = _colunas_formula(ws, linha_modelo, ws.max_column)
    _escrever_linhas_brutas(ws, linha_inicio, df, mapa, linha_modelo)
    for offset in range(len(df)):
        _arrastar_linha(ws, linha_modelo, linha_inicio + offset, colunas_formula)

    # Check (informativo — não é uma comparação automática contra o gráfico
    # "Digitação x Dia" do Looker, que é uma tile separada ainda não mapeada;
    # ver conversa com o usuário 2026-09-24): imprime os números pra
    # conferência visual rápida contra a tela do Looker.
    pagas = df[df["Status Proposta"] == "PROPOSTA PAGA"]
    soma_vl_financiamento_pagas = pagas["Vl Financiamento"].apply(_num).sum()

    return {
        "aba": "db_pagasanalitico",
        "periodo": dia.isoformat(),
        "linhas_baixadas": len(df),
        "linhas_paga": len(pagas),
        "soma_vl_financiamento_paga": round(soma_vl_financiamento_pagas, 2),
    }


def _normalizar_texto_numerico(serie: pd.Series) -> pd.Series:
    """Normaliza uma coluna que deveria ser texto (ex.: "Anomes Apuracao",
    comparada por igualdade exata de string) mas que o pandas pode ter lido
    como float64 — típico quando o CSV/Excel baixado do Looker tem alguma
    célula vazia nessa coluna (ex.: linha de total/rodapé), o que promove a
    coluna INTEIRA pra float64: um valor como 202609 vira 202609.0, e
    `.astype(str)` gera "202609.0" em vez de "202609", quebrando silenciosamente
    qualquer comparação de string exata (foi exatamente isso que zerou o
    resultado no primeiro teste real contra o portal em 2026-09-24: 430 linhas
    baixadas, 0 batendo com "202609"). NaN vira string vazia (nunca bate com
    nada — não queremos escrever uma linha de total/rodapé como se fosse dado)."""

    def normalizar(v: object) -> str:
        if pd.isna(v):
            return ""
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v).strip()

    return serie.map(normalizar)


def _num(v: object) -> float:
    from app.services.connectors.base import parse_looker_number

    if v is None or (isinstance(v, float) and pd.isna(v)):
        return 0.0
    try:
        return parse_looker_number(v)
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# db_apuracaoavista (grão: mês/Anomes) — comissao_avista / analitico
#
# ATENÇÃO: esta é a aba que `base_final` referencia por POSIÇÃO (não por
# XLOOKUP) — só atualiza se o mês pedido for o ÚLTIMO bloco da aba. Depois de
# rodar isso, `arrastar_base_final` PRECISA rodar em seguida pra criar as
# linhas novas correspondentes em `base_final`.
# ---------------------------------------------------------------------------


def atualizar_db_apuracaoavista(
    wb,
    anomes: str,
    *,
    sessao: tuple[PortalRpaConnector, Page] | None = None,
    evidencias: list[Path] | None = None,
) -> dict:
    """`anomes` no formato 'AAAAMM' (ex.: '202609')."""

    ws = wb["db_apuracaoavista"]
    header_row = 1
    mapa = _header_map(ws, header_row)
    col_anomes = mapa["Anomes Apuracao"]

    ultima = _ultima_linha_com_dado(ws, col_anomes, header_row)
    if ultima > header_row:
        ultimo_anomes = str(ws.cell(row=ultima, column=col_anomes).value)
        if anomes < ultimo_anomes:
            raise AtualizacaoRecusada(
                f"O mês {anomes} é anterior ao último mês já presente em db_apuracaoavista "
                f"({ultimo_anomes}). Essa aba só pode ser atualizada no mês mais recente — "
                "base_final referencia ela por posição de linha, então mexer no meio "
                "deslocaria todo o base_final calculado depois desse ponto. Não vou mexer nada."
            )

    bloco = _bloco_final_que_bate(
        ws, header_row, ultima, col_anomes, lambda v: str(v) == anomes
    )
    linha_modelo = ultima if ultima > header_row else None
    if bloco is not None:
        linha_modelo = bloco[0] - 1 if bloco[0] - 1 > header_row else linha_modelo

    if linha_modelo is None:
        raise AtualizacaoRecusada(
            "db_apuracaoavista está vazia — não há linha-modelo. Preencha ao menos 1 "
            "linha manualmente antes de rodar a automação."
        )

    # Baixa ANTES de mexer na planilha (ver mesma nota em atualizar_db_pagasanalitico).
    mes_fmt = f"{anomes[:4]}-{anomes[4:]}"  # "202609" -> "2026-09"
    df = baixar_looker_bruto(
        "comissao_avista",
        "analitico",
        filter_value_override=mes_fmt,
        sessao=sessao,
        evidencias=evidencias,
    )
    df["Anomes Apuracao"] = _normalizar_texto_numerico(df["Anomes Apuracao"])
    df = df[df["Anomes Apuracao"] == anomes].reset_index(drop=True)

    if bloco is not None:
        qtd_removida = bloco[1] - bloco[0] + 1
        ws.delete_rows(bloco[0], qtd_removida)
        linha_inicio = bloco[0]
        logger.info("db_apuracaoavista: removidas %d linhas antigas do mês %s antes de reinserir.", qtd_removida, anomes)
    else:
        linha_inicio = ultima + 1

    colunas_formula = _colunas_formula(ws, linha_modelo, ws.max_column)
    _escrever_linhas_brutas(ws, linha_inicio, df, mapa, linha_modelo)
    for offset in range(len(df)):
        _arrastar_linha(ws, linha_modelo, linha_inicio + offset, colunas_formula)

    # Check pedido pelo usuário: contagem do mês em db_apuracaoavista vs
    # contagem de "PROPOSTA PAGA" no MESMO mês em db_pagasanalitico. Se não
    # bater, não é necessariamente erro — pode só significar que essa aba
    # (apuração) ainda não sincronizou com a digitação, que atualiza com mais
    # frequência (ver mensagem do usuário, 2026-09-24).
    ano, mes = int(anomes[:4]), int(anomes[4:])
    qtd_pagas = _contar_pagas_pagasanalitico(wb, ano, mes)

    return {
        "aba": "db_apuracaoavista",
        "periodo": anomes,
        "linhas_baixadas": len(df),
        "qtd_proposta_paga_pagasanalitico_mesmo_mes": qtd_pagas,
        "contagens_batem": len(df) == qtd_pagas,
    }


# ---------------------------------------------------------------------------
# db_mercado (grão: mês) — painel_visita_mercado / analitico_mercado_por_loja
# ---------------------------------------------------------------------------


def atualizar_db_mercado(
    wb,
    anomes: str,
    *,
    sessao: tuple[PortalRpaConnector, Page] | None = None,
    evidencias: list[Path] | None = None,
) -> dict:
    """`anomes` no formato 'AAAAMM' (ex.: '202609'). Sem restrição de "só o
    último bloco" — nenhuma outra aba referencia `db_mercado` por posição."""
    ws = wb["db_mercado"]
    header_row = 1
    mapa = _header_map(ws, header_row)
    col_mes = mapa["Mês"]
    ano, mes = int(anomes[:4]), int(anomes[4:])

    def bate(v: object) -> bool:
        d = _as_date(v)
        return d is not None and d.year == ano and d.month == mes

    ultima = _ultima_linha_com_dado(ws, col_mes, header_row)
    if ultima > header_row:
        ultima_data = _as_date(ws.cell(row=ultima, column=col_mes).value)
        if ultima_data is not None and (ano, mes) < (ultima_data.year, ultima_data.month):
            raise AtualizacaoRecusada(
                f"O mês {anomes} é anterior ao último mês já presente em db_mercado "
                f"({ultima_data.year}-{ultima_data.month:02d}) e não está colado no final dos "
                "dados — mexer no meio da aba corromperia as fórmulas das linhas seguintes "
                "(ver docstring do módulo). Não vou mexer nada."
            )

    bloco = _bloco_final_que_bate(ws, header_row, ultima, col_mes, bate)
    linha_modelo = ultima if ultima > header_row else None
    if bloco is not None:
        linha_modelo = bloco[0] - 1 if bloco[0] - 1 > header_row else linha_modelo

    if linha_modelo is None:
        raise AtualizacaoRecusada(
            "db_mercado está vazia — não há linha-modelo. Preencha ao menos 1 linha "
            "manualmente antes de rodar a automação."
        )

    # Baixa ANTES de mexer na planilha (ver mesma nota em atualizar_db_pagasanalitico).
    filtro_base = (
        "R%24%2F%23=1&Dt+Refer%C3%AAncia+Month={mes}&Lojista=&Nome+GP=&SUPERVISOR="
        "&Nome+GN=&Nome+Filial=&Concession%C3%A1ria=&Auto+Shopping=&Plataforma="
        "&Uf+Loja=&Cidade+Loja=&Bairro+Loja="
    ).format(mes=f"{ano}-{mes:02d}")
    df = baixar_looker_bruto(
        "painel_visita_mercado",
        "analitico_mercado_por_loja",
        filter_query_override=filtro_base,
        sessao=sessao,
        evidencias=evidencias,
    )
    df["Mês"] = pd.to_datetime(df["Mês"]).dt.date
    df = df[df["Mês"].apply(lambda d: d.year == ano and d.month == mes)].reset_index(drop=True)

    if bloco is not None:
        qtd_removida = bloco[1] - bloco[0] + 1
        ws.delete_rows(bloco[0], qtd_removida)
        linha_inicio = bloco[0]
        logger.info("db_mercado: removidas %d linhas antigas do mês %s antes de reinserir.", qtd_removida, anomes)
    else:
        linha_inicio = ultima + 1

    colunas_formula = _colunas_formula(ws, linha_modelo, ws.max_column)
    _escrever_linhas_brutas(ws, linha_inicio, df, mapa, linha_modelo)
    for offset in range(len(df)):
        _arrastar_linha(ws, linha_modelo, linha_inicio + offset, colunas_formula)

    # Recontagem real (lê de volta o que ficou gravado na aba, não reusa
    # `len(df)`) — é isso que de fato verifica se a escrita funcionou, não
    # uma tautologia comparando o mesmo número consigo mesmo.
    linhas_registradas = sum(
        1
        for r in range(linha_inicio, linha_inicio + len(df))
        if bate(ws.cell(row=r, column=col_mes).value)
    )

    return {
        "aba": "db_mercado",
        "periodo": anomes,
        "linhas_baixadas": len(df),
        "linhas_registradas": linhas_registradas,
        "check_quantidade_bate": linhas_registradas == len(df),
    }


def _contar_pagas_pagasanalitico(wb, ano: int, mes: int) -> int:
    """Conta linhas de `db_pagasanalitico` com Status Proposta == 'PROPOSTA
    PAGA' no mês/ano dados — lê o que já está na aba (não baixa de novo)."""
    ws = wb["db_pagasanalitico"]
    mapa = _header_map(ws, 1)
    col_dt = mapa["Dt Relatório"]
    col_status = mapa["Status Proposta"]
    total = 0
    for r in range(2, ws.max_row + 1):
        d = _as_date(ws.cell(row=r, column=col_dt).value)
        if d is None:
            continue
        if d.year == ano and d.month == mes and ws.cell(row=r, column=col_status).value == "PROPOSTA PAGA":
            total += 1
    return total


# ---------------------------------------------------------------------------
# base_final — "arrastar" as fórmulas até acompanhar db_apuracaoavista
# ---------------------------------------------------------------------------


def arrastar_base_final(wb) -> dict:
    """
    `base_final` referencia `db_apuracaoavista` por POSIÇÃO: a linha N do
    base_final corresponde à linha N-1 de db_apuracaoavista (confirmado
    inspecionando a planilha real — ex.: base_final!O3974 = "=db_apuracaoavista!F3973").
    Depois de atualizar db_apuracaoavista, chame esta função pra criar as
    linhas novas de base_final que faltam, copiando a fórmula da última linha
    já existente (Translator — ver docstring do módulo).
    """
    ws_bf = wb["base_final"]
    ws_av = wb["db_apuracaoavista"]

    mapa_bf = _header_map(ws_bf, 2)  # cabeçalho de verdade fica na linha 2 (linha 1 é o grupo)
    col_cod_contrato = mapa_bf["COD_CONTRATO"]
    ultima_bf = _ultima_linha_com_dado(ws_bf, col_cod_contrato, header_row=2)

    mapa_av = _header_map(ws_av, 1)
    col_cd_contrato_av = mapa_av["Cd Contrato"]
    ultima_av = _ultima_linha_com_dado(ws_av, col_cd_contrato_av, header_row=1)

    alvo_bf = ultima_av + 1  # deslocamento de +1 confirmado na inspeção real
    if alvo_bf < ultima_bf:
        raise AtualizacaoRecusada(
            f"base_final tem mais linhas ({ultima_bf}) do que db_apuracaoavista suporta "
            f"(deveria ir até {alvo_bf}) — isso não deveria acontecer nunca; pare e investigue "
            "manualmente antes de continuar (pode ser sinal de uma edição manual fora do padrão)."
        )
    if alvo_bf == ultima_bf:
        return {"aba": "base_final", "linhas_adicionadas": 0, "ultima_linha": ultima_bf}

    if ultima_bf <= 2:
        raise AtualizacaoRecusada(
            "base_final não tem nenhuma linha de dado ainda — não há linha-modelo pra arrastar."
        )

    colunas_formula = _colunas_formula(ws_bf, ultima_bf, ws_bf.max_column)
    linhas_adicionadas = alvo_bf - ultima_bf
    for nova_linha in range(ultima_bf + 1, alvo_bf + 1):
        _arrastar_linha(ws_bf, ultima_bf, nova_linha, colunas_formula)

    logger.info(
        "base_final: %d linha(s) nova(s) arrastada(s) (de %d até %d), acompanhando db_apuracaoavista até a linha %d.",
        linhas_adicionadas,
        ultima_bf + 1,
        alvo_bf,
        ultima_av,
    )
    return {"aba": "base_final", "linhas_adicionadas": linhas_adicionadas, "ultima_linha": alvo_bf}
