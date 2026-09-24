"""
Monta o mini-relatório impresso ao final de `atualizar_excel.py` — lê os
dicts de resultado já devolvidos por cada `atualizar_db_*`/`arrastar_base_final`
(ver `excel_sync.py`) e formata de um jeito legível, junto com os caminhos dos
prints de evidência (ver `_tirar_print_evidencia` em `excel_sync.py`).

Os checks aqui são os que JÁ existem hoje — auto-consistência ENTRE abas da
própria planilha (ex.: contagem de db_apuracaoavista vs. PROPOSTA PAGA em
db_pagasanalitico), não uma comparação direta contra os números que o Looker
mostra na tela (isso exigiria mapear mais 2 tiles, deixado de fora por
decisão do usuário em 2026-09-24 — ver skill `project-context`).
"""

from datetime import datetime
from pathlib import Path


def _fmt_moeda(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _linhas_pagasanalitico(res: dict) -> list[str]:
    return [
        f"  {res['linhas_baixadas']} linha(s) baixada(s) do Looker | "
        f"{res['linhas_paga']} PROPOSTA PAGA | "
        f"soma Vl Financiamento (paga): {_fmt_moeda(res['soma_vl_financiamento_paga'])}",
        "  [INFO] sem comparação automática contra o Looker ainda — confira "
        'visualmente contra os gráficos "Digitação x Dia" e "(R$) Produção".',
    ]


def _linhas_apuracaoavista(res: dict) -> list[str]:
    bate = res["contagens_batem"]
    marca = "[OK]" if bate else "[INFO]"
    detalhe = (
        "contagem bate"
        if bate
        else (
            "contagem NÃO bate — não é necessariamente erro: pode só significar que "
            "esta apuração ainda não sincronizou com a digitação (que atualiza mais rápido)"
        )
    )
    return [
        f"  {res['linhas_baixadas']} linha(s) baixada(s) | "
        f"{res['qtd_proposta_paga_pagasanalitico_mesmo_mes']} PROPOSTA PAGA em "
        "db_pagasanalitico no mesmo mês",
        f"  {marca} {detalhe}",
    ]


def _linhas_mercado(res: dict) -> list[str]:
    bate = res["check_quantidade_bate"]
    marca = "[OK]" if bate else "[ATENÇÃO]"
    detalhe = (
        "contagem bate"
        if bate
        else "contagem NÃO bate — isso é inesperado, vale investigar (diferente do "
        "check de db_apuracaoavista, aqui não deveria haver descompasso)"
    )
    return [
        f"  {res['linhas_baixadas']} linha(s) baixada(s) | {res['linhas_registradas']} registrada(s) na planilha",
        f"  {marca} {detalhe}",
    ]


def _linhas_base_final(res: dict) -> list[str]:
    return [f"  {res['linhas_adicionadas']} linha(s) nova(s) arrastada(s), até a linha {res['ultima_linha']}."]


_FORMATADORES = {
    "db_pagasanalitico": _linhas_pagasanalitico,
    "db_apuracaoavista": _linhas_apuracaoavista,
    "db_mercado": _linhas_mercado,
    "base_final": _linhas_base_final,
}


def gerar_relatorio(resultados: list[dict], evidencias: list[Path] | None = None) -> str:
    """Monta o texto do mini-relatório a partir dos dicts de resultado de
    cada `atualizar_*`/`arrastar_base_final` chamado nessa execução, mais os
    caminhos dos prints de evidência (se algum foi tirado)."""
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    titulo = f" RELATÓRIO DE ATUALIZAÇÃO — {agora} "
    linhas = [titulo.center(70, "="), ""]

    for res in resultados:
        aba = res["aba"]
        periodo = res.get("periodo", "")
        cabecalho = f"{aba} ({periodo})" if periodo else aba
        linhas.append(cabecalho)
        formatador = _FORMATADORES.get(aba)
        linhas.extend(formatador(res) if formatador else [f"  {res}"])
        linhas.append("")

    if evidencias:
        linhas.append("Evidências (print do dashboard Looker no momento do download):")
        for caminho in evidencias:
            linhas.append(f"  - {caminho}")
        linhas.append("")

    linhas.append("=" * 70)
    return "\n".join(linhas)
