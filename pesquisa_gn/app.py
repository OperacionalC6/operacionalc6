"""
Pesquisa de Mercado - Gerentes de Negócio (GNs)
Setor automotivo e duas rodas.

Rodar localmente:   streamlit run app.py
Veja o README.md para publicar no Streamlit Community Cloud.
"""

from __future__ import annotations

import io
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

# =============================================================================
# CONFIGURAÇÕES (edite aqui)
# =============================================================================

BASE_DIR = Path(__file__).parent
# Base de Áreas/Lojistas: planilha com as colunas "ÁREA DO GN" e "LOJISTA".
# LOJISTA no formato "12345 - NOME" ou "12345 - (GRUPO X) - NOME".
# Para atualizar, basta substituir este arquivo mantendo as colunas.
LOJISTAS_XLSX = BASE_DIR / "lojistas.xlsx"
SEM_GRUPO = "SEM GRUPO"
RESPOSTAS_CSV = BASE_DIR / "data" / "respostas.csv"
FUSO = ZoneInfo("America/Sao_Paulo")

BANCOS_POS1 = ["Banco Honda", "Banco Yamaha", "Bradesco", "BV", "Carbank",
               "Itaú", "Pan", "Safra", "Santander", "Outros"]
BANCOS_POS2 = ["Banco Honda", "Banco Yamaha", "Bradesco", "BV", "Carbank",
               "Itaú", "Pan", "Safra", "Santander", "Stellantis", "Outros"]
BANCOS_POS3 = BANCOS_POS2

QUEM_RECEBE = ["Vendedor", "Lojista", "F&I", "Outros"]
OPCOES_QTD = [str(i) for i in range(1, 10)] + ["10+"]
VOLUME_MAX = 1000

# Ordem das colunas na planilha final
COLUNAS = [
    "data_hora", "area_gn", "codigo_lojista", "grupo", "lojista",
    "banco_1", "banco_2", "banco_3",
    "acordo_banco_1", "acordo_banco_2", "acordo_banco_3",
    "recompensa_banco_1", "recompensa_banco_2", "recompensa_banco_3",
    "quem_recebe_recompensa", "posicao_c6",
    "carros_mes", "motos_mes", "financiamentos_mes",
    "possui_fi", "qtd_fi", "qtd_vendedores", "qtd_lojas",
    "proposta_acao",
]

# =============================================================================
# PÁGINA / ESTILO (mobile-first)
# =============================================================================

st.set_page_config(page_title="C6 Auto · Pesquisa GN", page_icon="🚗", layout="centered",
                   initial_sidebar_state="collapsed")

LOGO = BASE_DIR / "logo.png"  # opcional: coloque o logo oficial com este nome

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
      html, body, [class*="css"], .stMarkdown, .stTextInput, .stSelectbox, button {
        font-family: 'Inter', sans-serif !important;
      }
      .block-container {max-width: 720px; padding-top: 1.2rem; padding-bottom: 4rem;}
      header[data-testid="stHeader"] {background: transparent;}

      /* Cabeçalho da marca */
      .c6-header {padding: 1.4rem 0 1.2rem; border-bottom: 1px solid #2A2A2A; margin-bottom: 1.2rem;}
      .c6-logo {font-size: 2.1rem; font-weight: 800; letter-spacing: -0.04em; line-height: 1; color: #FFF;}
      .c6-logo span {font-weight: 400; color: #A3A3A3;}
      .c6-sub {color: #A3A3A3; font-size: .95rem; margin-top: .45rem;}

      /* Títulos de seção */
      h3 {font-size: .8rem !important; font-weight: 600 !important; text-transform: uppercase;
          letter-spacing: .12em; color: #A3A3A3 !important; margin-top: 1.6rem !important;}

      /* Campos */
      div[data-baseweb="select"] > div, .stNumberInput input, .stTextInput input, .stTextArea textarea {
        min-height: 2.9rem; border-radius: 12px !important; background: #141414 !important;
        border-color: #2A2A2A !important;
      }
      div[data-testid="stExpander"] {border: 1px solid #2A2A2A; border-radius: 16px; background: #0B0B0B;}

      /* Botões: brancos com texto preto, cantos arredondados */
      .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
        min-height: 3.2rem; border-radius: 999px; font-weight: 700; letter-spacing: .01em;
      }
      .stButton > button[kind="primary"], .stFormSubmitButton > button,
      .stDownloadButton > button {
        background: #FFFFFF !important; color: #000000 !important; border: none !important;
      }
      .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button:hover,
      .stDownloadButton > button:hover {background: #D9D9D9 !important;}
      .stButton > button[kind="primary"] p, .stFormSubmitButton > button p,
      .stDownloadButton > button p {color: #000000 !important;}

      /* Indicadores do painel */
      div[data-testid="stMetric"] {background: #141414; border: 1px solid #2A2A2A;
        border-radius: 16px; padding: .9rem 1rem;}

      @media (max-width: 640px) {
        .block-container {padding-left: 1rem; padding-right: 1rem;}
        .c6-logo {font-size: 1.8rem;}
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def cabecalho(subtitulo: str):
    if LOGO.exists():
        st.image(str(LOGO), width=140)
        st.markdown(f'<div class="c6-sub">{subtitulo}</div>', unsafe_allow_html=True)
        st.markdown('<div class="c6-header" style="padding:0"></div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f'''<div class="c6-header"><div class="c6-logo">C6 <span>Auto</span></div>
            <div class="c6-sub">{subtitulo}</div></div>''',
            unsafe_allow_html=True,
        )


# =============================================================================
# DADOS: lojistas e armazenamento de respostas
# =============================================================================


def separar_lojista(texto: str) -> tuple[str, str, str]:
    """'12345 - (GRUPO X) - NOME' -> ('12345', 'GRUPO X', 'NOME')."""
    codigo, _, resto = str(texto).partition(" - ")
    resto = resto.strip()
    grupo = SEM_GRUPO
    m = re.match(r"^\((.+?)\)\s*-\s*(.*)$", resto)
    if m:
        grupo, resto = m.group(1).strip(), m.group(2).strip()
    return codigo.strip(), grupo, resto


@st.cache_data(ttl=300)
def carregar_lojistas() -> pd.DataFrame:
    bruto = pd.read_excel(LOJISTAS_XLSX, dtype=str).dropna(how="all")
    col_area, col_loj = bruto.columns[:2]  # 1ª coluna: área; 2ª: lojista
    bruto = bruto.dropna(subset=[col_area, col_loj])
    partes = bruto[col_loj].map(separar_lojista)
    df = pd.DataFrame({
        "area": bruto[col_area].str.strip(),
        "codigo": partes.str[0], "grupo": partes.str[1], "nome": partes.str[2],
    })
    df["rotulo"] = df["codigo"] + " - " + df["grupo"] + " - " + df["nome"]
    return df.drop_duplicates(subset=["area", "codigo"]).reset_index(drop=True)


def segredo(chave: str, padrao=None):
    try:
        return st.secrets[chave]
    except Exception:
        return os.environ.get(chave, padrao)


def credenciais_google() -> dict | None:
    """Aceita o .json inteiro colado em GOOGLE_JSON ou o bloco [gcp_service_account]."""
    bruto = segredo("GOOGLE_JSON")
    if bruto:
        import json
        return json.loads(bruto)
    bloco = segredo("gcp_service_account")
    return dict(bloco) if bloco else None


def usa_google_sheets() -> bool:
    return segredo("gsheets") is not None and credenciais_google() is not None


@st.cache_resource
def _worksheet():
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_info(
        credenciais_google(),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    sh = gspread.authorize(creds).open_by_url(st.secrets["gsheets"]["spreadsheet_url"])
    nome = st.secrets["gsheets"].get("worksheet", "Respostas")
    try:
        ws = sh.worksheet(nome)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=nome, rows=1000, cols=len(COLUNAS))
    if ws.row_values(1) != COLUNAS:  # cria ou atualiza o cabeçalho
        ws.update(values=[COLUNAS], range_name="A1")
    return ws


def salvar_resposta(registro: dict) -> None:
    linha = [registro.get(c, "") for c in COLUNAS]
    if usa_google_sheets():
        _worksheet().append_row(linha, value_input_option="USER_ENTERED")
        return
    RESPOSTAS_CSV.parent.mkdir(parents=True, exist_ok=True)
    if RESPOSTAS_CSV.exists():
        cabecalho_atual = pd.read_csv(RESPOSTAS_CSV, sep=";", encoding="utf-8-sig", nrows=0)
        if list(cabecalho_atual.columns) != COLUNAS:  # layout mudou: arquiva o antigo
            RESPOSTAS_CSV.rename(RESPOSTAS_CSV.with_name(
                f"respostas_antigo_{datetime.now(FUSO):%Y%m%d_%H%M%S}.csv"))
    novo = not RESPOSTAS_CSV.exists()
    pd.DataFrame([linha], columns=COLUNAS).to_csv(
        RESPOSTAS_CSV, mode="a", header=novo, index=False, sep=";", encoding="utf-8-sig"
    )


def carregar_respostas() -> pd.DataFrame:
    if usa_google_sheets():
        df = pd.DataFrame(_worksheet().get_all_records())
    elif RESPOSTAS_CSV.exists():
        df = pd.read_csv(RESPOSTAS_CSV, sep=";", encoding="utf-8-sig", dtype=str)
    else:
        df = pd.DataFrame(columns=COLUNAS)
    for col in ["posicao_c6", "carros_mes", "motos_mes", "financiamentos_mes"]:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# =============================================================================
# FORMULÁRIO DO GN
# =============================================================================

CAMPOS_FORM = [
    "area", "lojista", "b1", "b2", "b3", "b1_outro", "b2_outro", "b3_outro",
    "ac1", "ac2", "ac3", "rec1", "rec2", "rec3", "quem", "quem_outro", "pos_c6",
    "carros", "motos", "fin", "possui_fi", "qtd_fi", "qtd_vend", "qtd_lojas", "proposta",
]


def limpar_formulario():
    for k in CAMPOS_FORM:
        st.session_state.pop(k, None)


def nome_banco(pos: int) -> str:
    banco = st.session_state.get(f"b{pos}")
    if banco == "Outros":
        outro = (st.session_state.get(f"b{pos}_outro") or "").strip()
        return f"Outros: {outro}" if outro else "Outros"
    return banco or ""


def seletor_banco(pos: int, opcoes: list[str]):
    st.selectbox(f"Banco Posição {pos} *", opcoes, index=None,
                 placeholder="Selecione o banco", key=f"b{pos}")
    if st.session_state.get(f"b{pos}") == "Outros":
        st.text_input(f"Qual banco (Posição {pos})?", key=f"b{pos}_outro")


def pagina_formulario():
    cabecalho("Pesquisa de Mercado · Gerentes de Negócio")
    st.caption("Campos com * são obrigatórios.")

    if st.session_state.pop("enviado_ok", False):
        st.success("✅ Resposta enviada com sucesso! Obrigado. Você já pode preencher outra.")

    lojistas = carregar_lojistas()

    # 1-2. Área e Lojista ----------------------------------------------------
    st.subheader("Identificação")
    areas = sorted(lojistas["area"].unique())
    area = st.selectbox("Área do GN *", areas, index=None,
                        placeholder="Selecione sua área", key="area",
                        on_change=lambda: st.session_state.pop("lojista", None))
    filtrados = lojistas[lojistas["area"] == area] if area else lojistas.iloc[0:0]
    rotulos = dict(zip(filtrados["codigo"], filtrados["rotulo"]))
    st.selectbox("Lojista (Código - Grupo - Nome) *", list(rotulos), index=None,
                 format_func=lambda c: rotulos.get(c, c),
                 placeholder="Selecione a área primeiro" if not area
                 else "Busque pelo código, grupo ou nome",
                 disabled=not area, key="lojista")

    # 3-5. Bancos, acordos e recompensas -------------------------------------
    st.subheader("Bancos")
    for pos, opcoes in [(1, BANCOS_POS1), (2, BANCOS_POS2), (3, BANCOS_POS3)]:
        with st.expander(f"Banco Posição {pos}", expanded=True):
            seletor_banco(pos, opcoes)
            st.text_area(f"Acordos – Banco {pos}", key=f"ac{pos}", height=80,
                         placeholder="Ex.: Plus por contrato, Plus por valor - % de Plus, taxa diferenciada...")
            st.text_area(f"Programa de Recompensa – Banco {pos}", key=f"rec{pos}", height=80,
                         placeholder="Ex.: R$ 50 por contrato, viagem...")

    st.radio("Quem recebe o programa de recompensa? *", QUEM_RECEBE, index=None,
             horizontal=True, key="quem")
    if st.session_state.get("quem") == "Outros":
        st.text_input("Quem?", key="quem_outro")

    st.slider("Posição do Banco C6 *", min_value=1, max_value=10, value=1, key="pos_c6",
              help="1 = principal banco da loja; 10 = menos utilizado.")

    # 8. Volumetria ----------------------------------------------------------
    st.subheader("Volumetria mensal (média)")
    c1, c2, c3 = st.columns(3)
    c1.number_input("Carros vendidos", 0, VOLUME_MAX, 0, step=1, key="carros")
    c2.number_input("Motos vendidas", 0, VOLUME_MAX, 0, step=1, key="motos")
    c3.number_input("Financiamentos", 0, VOLUME_MAX, 0, step=1, key="fin")

    # 9. Estrutura de vendas -------------------------------------------------
    st.subheader("Estrutura de vendas")
    possui_fi = st.radio("Possui F&I? *", ["Sim", "Não"], index=None, horizontal=True,
                         key="possui_fi")
    if possui_fi == "Sim":
        st.selectbox("Quantidade de F&I *", OPCOES_QTD, index=None,
                     placeholder="Selecione", key="qtd_fi")
    c4, c5 = st.columns(2)
    c4.selectbox("Qtd. de Vendedores *", OPCOES_QTD, index=None,
                 placeholder="Selecione", key="qtd_vend")
    c5.selectbox("Qtd. de Lojas *", OPCOES_QTD, index=None,
                 placeholder="Selecione", key="qtd_lojas")

    # 10. Proposta -----------------------------------------------------------
    st.subheader("Proposta de ação")
    st.text_area("Proposta de Ação (opcional)", key="proposta", height=120)

    st.divider()
    if st.button("Enviar resposta", type="primary", width="stretch"):
        enviar()


def validar() -> list[str]:
    s = st.session_state
    erros = []
    obrig = {
        "area": "Área do GN", "lojista": "Lojista", "b1": "Banco Posição 1",
        "b2": "Banco Posição 2", "b3": "Banco Posição 3",
        "quem": "Quem recebe o programa de recompensa", "possui_fi": "Possui F&I",
        "qtd_vend": "Quantidade de Vendedores", "qtd_lojas": "Quantidade de Lojas",
    }
    erros += [f"Preencha: **{rotulo}**" for k, rotulo in obrig.items() if not s.get(k)]
    if s.get("possui_fi") == "Sim" and not s.get("qtd_fi"):
        erros.append("Preencha: **Quantidade de F&I**")

    for pos in (1, 2, 3):
        if s.get(f"b{pos}") == "Outros" and not (s.get(f"b{pos}_outro") or "").strip():
            erros.append(f"Informe qual é o banco 'Outros' da **Posição {pos}**")
    bancos = [nome_banco(p) for p in (1, 2, 3) if s.get(f"b{p}")]
    if len(bancos) != len(set(b.lower() for b in bancos)):
        erros.append("O mesmo banco foi escolhido em mais de uma posição.")

    for k, rotulo in [("carros", "Carros"), ("motos", "Motos"), ("fin", "Financiamentos")]:
        v = s.get(k)
        if v is None or not 0 <= v <= VOLUME_MAX:
            erros.append(f"**{rotulo}** deve estar entre 0 e {VOLUME_MAX}.")
    return erros


def enviar():
    erros = validar()
    if erros:
        st.error("Corrija os itens abaixo antes de enviar:\n\n" +
                 "\n".join(f"- {e}" for e in erros))
        return

    s = st.session_state
    lojistas = carregar_lojistas()
    loja = lojistas[(lojistas["area"] == s["area"]) & (lojistas["codigo"] == s["lojista"])].iloc[0]
    quem = s["quem"]
    if quem == "Outros" and (s.get("quem_outro") or "").strip():
        quem = f"Outros: {s['quem_outro'].strip()}"

    registro = {
        "data_hora": datetime.now(FUSO).strftime("%d/%m/%Y %H:%M:%S"),
        "area_gn": s["area"], "codigo_lojista": loja["codigo"], "grupo": loja["grupo"],
        "lojista": loja["nome"],
        "banco_1": nome_banco(1), "banco_2": nome_banco(2), "banco_3": nome_banco(3),
        "acordo_banco_1": s.get("ac1", "").strip(),
        "acordo_banco_2": s.get("ac2", "").strip(),
        "acordo_banco_3": s.get("ac3", "").strip(),
        "recompensa_banco_1": s.get("rec1", "").strip(),
        "recompensa_banco_2": s.get("rec2", "").strip(),
        "recompensa_banco_3": s.get("rec3", "").strip(),
        "quem_recebe_recompensa": quem, "posicao_c6": int(s["pos_c6"]),
        "carros_mes": int(s["carros"]), "motos_mes": int(s["motos"]),
        "financiamentos_mes": int(s["fin"]),
        "possui_fi": s["possui_fi"],
        "qtd_fi": s.get("qtd_fi") if s["possui_fi"] == "Sim" else "0",
        "qtd_vendedores": s["qtd_vend"], "qtd_lojas": s["qtd_lojas"],
        "proposta_acao": s.get("proposta", "").strip(),
    }
    try:
        with st.spinner("Salvando..."):
            salvar_resposta(registro)
    except Exception as e:  # noqa: BLE001
        st.error(f"Não foi possível salvar a resposta. Tente novamente.\n\nDetalhe: {e}")
        return

    limpar_formulario()
    st.session_state["enviado_ok"] = True
    st.rerun()


# =============================================================================
# PAINEL DO GESTOR
# =============================================================================


def gerar_excel(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Respostas")
        ws = w.sheets["Respostas"]
        for col in ws.columns:
            largura = max(len(str(c.value or "")) for c in col[:200])
            ws.column_dimensions[col[0].column_letter].width = min(max(12, largura + 2), 50)
        ws.freeze_panes = "A2"
    return buf.getvalue()


def pagina_gestor():
    cabecalho("Painel do Gestor")

    senha_correta = segredo("ADMIN_PASSWORD", "gestor123")
    if not st.session_state.get("gestor_ok"):
        with st.form("login"):
            senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", width="stretch"):
                if senha == senha_correta:
                    st.session_state["gestor_ok"] = True
                    st.rerun()
                st.error("Senha incorreta.")
        if senha_correta == "gestor123":
            st.caption("⚠️ Usando a senha padrão. Defina ADMIN_PASSWORD nos Secrets.")
        return

    c_a, c_b = st.columns([3, 1])
    c_a.caption("Armazenamento: " + ("Google Sheets" if usa_google_sheets()
                                     else f"CSV local ({RESPOSTAS_CSV.name})"))
    if c_b.button("Sair", width="stretch"):
        st.session_state["gestor_ok"] = False
        st.rerun()

    df = carregar_respostas()
    if df.empty:
        st.info("Ainda não há respostas.")
        return

    # Filtros
    areas = sorted(df["area_gn"].dropna().unique())
    sel = st.multiselect("Filtrar por Área", areas, placeholder="Todas as áreas")
    if sel:
        df = df[df["area_gn"].isin(sel)]

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Respostas", len(df))
    k2.metric("Lojistas", df["codigo_lojista"].nunique())
    k3.metric("Posição média C6", f"{df['posicao_c6'].mean():.1f}" if len(df) else "-")
    k4.metric("Financ./mês (soma)", f"{int(df['financiamentos_mes'].sum()):,}".replace(",", "."))

    t1, t2, t3 = st.tabs(["📊 Resumo", "📋 Respostas", "⬇️ Download"])

    with t1:
        st.markdown("**Banco na Posição 1 (líder na loja)**")
        st.bar_chart(df["banco_1"].value_counts(), horizontal=True)

        st.markdown("**Presença dos bancos (posições 1 a 3)**")
        presenca = pd.concat([df["banco_1"], df["banco_2"], df["banco_3"]]).value_counts()
        st.bar_chart(presenca, horizontal=True)

        st.markdown("**Distribuição da posição do C6**")
        st.bar_chart(df["posicao_c6"].value_counts().sort_index())

        st.markdown("**Quem recebe a recompensa**")
        st.bar_chart(df["quem_recebe_recompensa"].value_counts(), horizontal=True)

        st.markdown("**Volumetria por Área (soma mensal)**")
        vol = df.groupby("area_gn")[["carros_mes", "motos_mes", "financiamentos_mes"]].sum()
        st.dataframe(vol, width="stretch")

    with t2:
        st.dataframe(df, width="stretch", hide_index=True)

    with t3:
        agora = datetime.now(FUSO).strftime("%Y%m%d_%H%M")
        st.download_button("📗 Baixar Excel (.xlsx)", gerar_excel(df),
                           file_name=f"pesquisa_gn_{agora}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           width="stretch")
        st.download_button("📄 Baixar CSV (;)",
                           df.to_csv(index=False, sep=";").encode("utf-8-sig"),
                           file_name=f"pesquisa_gn_{agora}.csv", mime="text/csv",
                           width="stretch")


# =============================================================================
# NAVEGAÇÃO
# =============================================================================

modo = st.segmented_control("Navegação", ["Formulário", "Gestor"],
                            default="Formulário", label_visibility="collapsed")
if modo == "Gestor":
    pagina_gestor()
else:
    pagina_formulario()
