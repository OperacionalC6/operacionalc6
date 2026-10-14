# Pesquisa de Mercado – GNs (Streamlit)

Formulário web (otimizado para celular) para os Gerentes de Negócio registrarem
a pesquisa de mercado dos lojistas, com painel do gestor protegido por senha
(resumo + download em Excel/CSV).

```
pesquisa_gn/
├── app.py                          # aplicação
├── lojistas.xlsx                   # Áreas e Lojistas (edite aqui)
├── requirements.txt
└── .streamlit/
    ├── config.toml                 # tema
    └── secrets.toml.example        # modelo de senha / Google Sheets
```

## Como personalizar

| O que mudar                        | Onde                                                        |
|------------------------------------|-------------------------------------------------------------|
| Áreas do GN e lojistas             | `lojistas.xlsx` (colunas `ÁREA DO GN` e `LOJISTA` — basta substituir o arquivo) |
| Listas de bancos, opções, limites  | Bloco **CONFIGURAÇÕES** no topo de `app.py`                 |
| Senha do gestor                    | `ADMIN_PASSWORD` em `.streamlit/secrets.toml` ou nos Secrets do Cloud |

As áreas do dropdown são lidas automaticamente do `lojistas.xlsx` — basta
adicionar linhas com uma área nova.

## Opção A – Rodar no seu computador

1. Instale o Python 3.10+ (https://www.python.org/downloads/ — marque "Add to PATH").
2. Abra o terminal na pasta `pesquisa_gn` e rode:
   ```bash
   pip install -r requirements.txt
   copy .streamlit\secrets.toml.example .streamlit\secrets.toml   # Windows
   # cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # Mac/Linux
   streamlit run app.py
   ```
3. Edite `.streamlit/secrets.toml` e troque `ADMIN_PASSWORD`.
4. Abre em `http://localhost:8501`. Para os GNs acessarem pelo celular na mesma
   rede, use o endereço "Network URL" que aparece no terminal.

As respostas ficam em `data/respostas.csv` (separador `;`, abre direto no Excel).

## Opção B – Streamlit Community Cloud (grátis, link público)

1. Suba este repositório no GitHub (já está).
2. Acesse https://share.streamlit.io, entre com o GitHub e clique **Create app**.
3. Escolha o repositório, a branch e em **Main file path** coloque
   `pesquisa_gn/app.py`.
4. Em **Advanced settings → Secrets**, cole o conteúdo de
   `.streamlit/secrets.toml.example` com sua senha (e o bloco do Google Sheets,
   veja abaixo).
5. Clique **Deploy**. Envie o link gerado para os GNs.

> ⚠️ **Importante:** no Streamlit Cloud o disco é temporário — o CSV local é
> **apagado** sempre que o app reinicia ou dorme. Para uso real no Cloud,
> configure o Google Sheets (abaixo). Localmente o CSV funciona normalmente.

## Salvar em Google Sheets (recomendado no Cloud)

1. Em https://console.cloud.google.com crie um projeto e ative a
   **Google Sheets API**.
2. Em **IAM & Admin → Service Accounts**, crie uma conta de serviço →
   aba **Keys → Add key → JSON**. Um arquivo `.json` será baixado.
3. Crie uma planilha no Google Sheets e **compartilhe** com o e-mail da conta de
   serviço (`...@...iam.gserviceaccount.com`) como **Editor**.
4. Nos Secrets, cole (trocando os valores):
   ```toml
   ADMIN_PASSWORD = "sua-senha"

   GOOGLE_JSON = '''
   { ...conteúdo inteiro do arquivo .json, de { até } ... }
   '''

   [gsheets]
   spreadsheet_url = "https://docs.google.com/spreadsheets/d/SEU_ID/edit"
   worksheet = "Respostas"
   ```
   `GOOGLE_JSON` precisa vir **antes** de `[gsheets]`. (O formato antigo,
   com o bloco `[gcp_service_account]` campo a campo, também funciona.)

Com isso configurado, o app grava automaticamente na planilha (aba
`Respostas`, criada com cabeçalho se não existir) e o painel do gestor lê de lá.
O painel mostra qual armazenamento está em uso.

## Uso

- **📝 Formulário** – o GN escolhe a área, o lojista (filtrado pela área) e
  preenche o resto. Validações: campos obrigatórios, volumes de 0 a 1000,
  bancos sem repetição entre posições, "Outros" exige o nome, quantidade de
  F&I só aparece se "Possui F&I = Sim". Após enviar, o formulário é limpo.
- **🔒 Gestor** – digite a senha para ver indicadores, gráficos (banco líder,
  presença dos bancos, posição do C6, quem recebe recompensa, volumetria por
  área), tabela completa e botões para baixar **Excel** ou **CSV**.
