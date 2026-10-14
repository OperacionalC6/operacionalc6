"""
Print dos 3 "dashboards" da aba ACOMP_DIARIO — pedido explícito do usuário
em 2026-09-25. Diferente do resto do módulo `excel_sync.py` (que usa
Playwright pra capturar o Looker), esses dashboards são só faixas de célula
formatadas dentro do próprio Construcao.xlsx, então aqui usamos automação
COM do Excel de verdade (pywin32) pra abrir o arquivo JÁ SALVO, deixar
recalcular (openpyxl não recalcula fórmula nenhuma), e tirar print de cada
intervalo via copiar-como-imagem + clipboard. Só funciona no Windows com
Excel instalado — é exatamente onde este projeto sempre roda (nunca em
nuvem, decisão de 2026-09-24, ver skill `project-context`).

Intervalos confirmados testando ao vivo com o usuário em 2026-09-25 (achou
os 3 blocos, ajustou a largura de cada um depois de ver o resultado real).
"""

import logging
import time
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)

_BLOCOS = {
    "acomp_diario_bloco1": "B7:AB27",
    "acomp_diario_bloco2": "AF7:AR27",
    "acomp_diario_bloco3": "B40:U60",
}


@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
def _capturar_bloco(ws, endereco: str):
    """CopyPicture + leitura do clipboard de 1 bloco só, com 1 nova
    tentativa automática — achado real em 2026-10-13: `Range.CopyPicture`
    pode falhar transitoriamente (`CopyPicture method of Range class
    failed`, erro COM clássico de automação do Excel, provavelmente ligado
    à janela do Excel ficar invisível durante a automação — `excel.Visible
    = False`) mesmo com a planilha certinha; uma 2ª tentativa resolve na
    maioria dos casos."""
    from PIL import ImageGrab

    rng = ws.Range(endereco)
    rng.CopyPicture(Appearance=1, Format=2)  # xlScreen, xlBitmap
    time.sleep(1)  # tempo do clipboard atualizar antes de ler
    img = ImageGrab.grabclipboard()
    if img is None:
        raise RuntimeError("Clipboard veio vazio depois do CopyPicture.")
    return img


def capturar_prints_acomp_diario(caminho_planilha: Path, destino_dir: Path) -> list[Path]:
    """Abre `caminho_planilha` (já salva) no Excel de verdade, somente
    leitura (não altera o arquivo), recalcula tudo, e tira print dos 3
    blocos da aba ACOMP_DIARIO. Devolve os caminhos dos PNGs gerados.

    Cada bloco é independente — uma falha num bloco (mesmo após a nova
    tentativa de `_capturar_bloco`) só pula ESSE bloco, não derruba os
    outros 2 (achado real em 2026-10-13: antes, 1 bloco falhando abortava a
    captura dos 3 inteira, já que o loop não tinha try/except nenhum). Só
    levanta exceção daqui se algo falhar ANTES de entrar no loop de blocos
    (ex.: não conseguir abrir o Excel/a planilha) — quem chama decide se
    trata como aviso (não deve derrubar a atualização de dado em si, que já
    terminou nesse ponto — ver uso em `app/atualizar_excel.py`)."""
    import win32com.client as win32

    destino_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    excel = win32.gencache.EnsureDispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False

    caminhos: list[Path] = []
    try:
        wb = excel.Workbooks.Open(str(caminho_planilha), ReadOnly=True, UpdateLinks=False)
        try:
            excel.CalculateFullRebuild()
            time.sleep(3)  # tempo extra pro recálculo de fórmulas pesadas assentar

            ws = wb.Sheets("ACOMP_DIARIO")
            for nome, endereco in _BLOCOS.items():
                try:
                    img = _capturar_bloco(ws, endereco)
                except Exception as exc:
                    logger.warning(
                        "Não consegui tirar o print de %s (%s), mesmo com nova tentativa — "
                        "pulando só esse bloco (não afeta a atualização de dado): %s",
                        nome,
                        endereco,
                        exc,
                    )
                    continue
                dest = destino_dir / f"{nome}_{timestamp}.png"
                img.save(dest)
                caminhos.append(dest)
        finally:
            wb.Close(SaveChanges=False)
    finally:
        excel.Quit()

    return caminhos
