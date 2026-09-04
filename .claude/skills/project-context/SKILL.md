---
name: project-context
description: Contexto e status atual do projeto operacionalc6 (plataforma interna de gestão do negócio de correspondente bancário C6 Consig). Consulte SEMPRE que for planejar próximos passos, decidir arquitetura, retomar o trabalho depois de um tempo parado, ou quando o usuário perguntar "onde paramos" / "o que falta" / "qual o plano". Também consulte antes de propor stack, hospedagem ou fluxo de autenticação novos — as decisões já foram tomadas e estão documentadas aqui, não redecida do zero.
---

# Contexto do projeto operacionalc6

## O que é

Plataforma interna para o dono do negócio (correspondente bancário C6 Consig, usuário: felipe.sguedes@gmail.com)
e seus consultores acompanharem métricas de comissão/produção, substituindo o processo atual de planilhas
alimentadas manualmente. Extrai dados via RPA de dois sistemas do C6 (WebAutorizador e dashboards Looker
embutidos), guarda num banco, expõe num painel web autenticado.

Branch de trabalho: `claude/previous-session-recovery-fv67s4`.

## Arquitetura decidida (não redecida sem necessidade)

- **Backend**: FastAPI + Postgres, já escrito em `backend/app/`. Auth via Google Sign-In + JWT próprio
  (implementado — ver `security-access` skill), RBAC (admin/gestor veem tudo, membro só vê sua equipe),
  log de auditoria, camada de conectores plugável (`DataConnector`: RPA hoje, API oficial do C6 como
  stub pra quando/se sair homologação).
- **O robô do RPA roda dentro do próprio serviço web**, não num worker separado — o agendador
  (`app/services/scheduler.py`, APScheduler) inicia junto com a API no `lifespan` do FastAPI
  (`app/main.py`). Um serviço só no Render (web) resolve API + robô; não precisa de Background Worker.
- **Frontend**: ainda não existe. Decidido: Next.js, hospedado na Vercel, **plano gratuito (Hobby)** —
  sem desvantagem prática pra esse projeto, migrar pra Pro é só questão de billing, não bloqueia nada.
- **Hospedagem backend+Postgres**: Render, **plano PAGO desde o início** (decisão do usuário em
  2026-08-18 — preferiu simplicidade de um provedor só a economizar rodando o robô localmente/banco
  temporário). Infra descrita como código em `render.yaml` (raiz do repo) — Blueprint do Render, cria
  o serviço web + Postgres automaticamente quando conectado ao repositório.
- **Domínio**: a empresa NÃO tem domínio próprio (usa Gmail pessoal). Decidido usar os subdomínios
  gratuitos do Render/Vercel por enquanto — domínio próprio é opcional, adicionar depois se quiser.
- **Autenticação**: login via Google Sign-In implementado (`POST /auth/google`) — sem senha própria no
  sistema. Autorização = existir um registro em `users` com `is_active=True` (mantido pelo admin via
  `POST /users`), não uma lista separada. Detalhes completos e o porquê na skill `security-access`.
- **Contas de nuvem**: TUDO deve ser criado com conta/e-mail da empresa, nunca a conta pessoal do usuário
  nem rodando na máquina dele. Código já está na organização GitHub `OperacionalC6` (transferido de
  `sguedesfelipe/operacionalc6` em 2026-08-18). Contas de Render/Vercel: ver "Status atual".

## Status atual (2026-09-03)

**Funcionando e validado contra o portal real:**
- Login no WebAutorizador (`backend/app/services/connectors/portal_rpa.py`)
- Acesso aos dashboards Looker (via bootstrap — ver skill `rpa-conventions`)
- **6 relatórios Looker mapeados** (todos com dados reais fornecidos pelo usuário, não seletores
  adivinhados — ver `portal_selectors.json`), **14 métricas distintas no total**:
  1. `comissao_avista` (dashboard `corp_consignado_embed::01526_auto`) — 4 tiles, 3 mapeadas
     (`comissao_avista`, `comissao_avista_detalhamento`, `comissao_avista_por_filial`); "Qtde por
     Alçadas" deixada pra depois (cabeçalho pivotado, precisa parsing especial).
  2. `apuracao_parceiro_resumo` (dashboard `corp_consignado_embed::01532_auto`) — 4 tiles, todas
     mapeadas: `comissao_liquida`, `comissao_carteira`, `producao`/`producao_por_filial`,
     `seguros`/`seguros_por_filial`.
  3. `acompanhamento_veiculos` (dashboard `corp_consignado_embed::00087`) — 1 tile mapeada
     (`digitacao_analitico`, dado por proposta individual, não apuração mensal). Abas "Digitação" e
     "Produção" do mesmo dashboard ainda não mapeadas.
  4. `painel_carteira` (dashboard `corp_consignado_embed::00235_auto`) — 1 tile mapeada
     (`mercado_potencial`).
  5. `apuracao_comissao_carteira` (dashboard `corp_consignado_embed::01512_auto`) — 2 tiles mapeadas
     (`comissao_carteira_detalhamento`, rollup; `carteira_saldo`, saldo de carteira, dado novo).
  6. `painel_visita_mercado` (dashboard `corp_consignado_embed::00305_visitas`) — 1 tile, 2 métricas
     (`mercado_producao_c6`, `mercado_financiamento_total`); usa `{current_month}` no `filter_query`
     porque o filtro é um mês fixo, não uma janela relativa.
- **Convenção importante** (ver `rpa-conventions` itens 16-17): quando
  uma tile é ROLLUP de outra já mapeada (mesma comissão/produção, granularidade diferente), o
  `metric_name` é sempre diferente pra não somar em dobro num total ingênuo — validado empiricamente
  (soma da versão "por filial" bate exatamente com a versão sem filial, conferido rodando o parser
  contra os arquivos reais antes de gravar qualquer coisa).
- `column_mapping` de uma tile pode ser um dict (1 métrica) ou uma lista de dicts (várias métricas do
  MESMO arquivo baixado) — extensão feita quando apareceu o primeiro caso real de tile com mais de um
  número que valia a pena virar métrica separada.
- Suporte a `filter_query` (URL de filtro completa, colada verbatim) além do `filter_param`/
  `filter_value` simples de antes — necessário pro relatório `acompanhamento_veiculos`, que tem
  dezenas de parâmetros de filtro.
- **Proteção contra duplicata/perda de dado** em `run_pipeline()`: cada rodada apaga as métricas já
  existentes daquela fonte na janela de datas antes de inserir as novas — idempotente, não empilha
  registro repetido rodando várias vezes.
- **2268 registros reais gravados em produção** (Postgres do Render) na validação completa dos 6
  relatórios (ver "Validação completa" abaixo).

**Pendente dentro dos relatórios já mapeados:**
- `column_mapping` da tile "Qtde por Alçadas" (comissao_avista) — arquivo já baixa certo, só não é
  parseado ainda (ver `portal_selectors.json`).
- Abas "Digitação" e "Produção" do dashboard `acompanhamento_veiculos` (só "Analítico" mapeada até
  agora).

**Validação "testar tudo isso contra produção agora" — CONCLUÍDA (2026-09-02/03):** 🎉
Pipeline manual rodado de ponta a ponta contra o banco de produção, cobrindo os 6 relatórios
mapeados (13 tiles). Dois bugs reais corrigidos no processo (aria-label de tile divergente do texto
visível, ver `rpa-conventions` item 18; flake intermitente de timeout no download, ver item 19 — retry
adicionado em `_download_tile`). Na rodada final, os 2 relatórios que nunca tinham sido exercitados
contra o portal real (`apuracao_comissao_carteira`, `painel_visita_mercado`) baixaram sem nenhum
mismatch de nome de tile. Resultado: **2268 registros ingeridos, zero erros**, substituindo os 486
registros da ingestão anterior (janela de 90 dias, fonte `portal_rpa`) — confirma que a proteção
idempotente contra duplicata (apagar+reinserir a janela) está funcionando como esperado mesmo com o
número de métricas tendo saltado de 9 pra 14.

**Feito (primeira ingestão real em produção, 2026-09-01):** 🎉
- Rodado manualmente (da máquina do usuário, reaproveitando o perfil de navegador já aprovado, gravando
  direto no Postgres de produção do Render via `run_pipeline()`) — **486 registros reais gravados em
  `metrics`**, confirmados aparecendo no dashboard (`https://operacionalc6.vercel.app/dashboard`).
- Três bugs reais encontrados e corrigidos nesse teste (só apareceram rodando contra produção de
  verdade — documentados em detalhe na skill `rpa-conventions`, itens 11-13):
  1. Filtro de período do Looker (`filter_value`) mudado de `"this month"` pra `"2 months"` — o mês
     corrente ainda não tinha apuração fechada.
  2. `download_wait_ms` aumentado de 20s pra 60s — tile mais pesada ainda estava renderizando quando o
     robô tentava baixar (suspeita, não 100% confirmada — ver item 12 da skill).
  3. Célula vazia numa coluna de dimensão virava `NaN` do pandas, gerando JSON inválido pro Postgres —
     corrigido convertendo pra `None`/`null`.
- **`app/core/config.py`**: corrigido pra aceitar `postgres://` (esquema curto, usado na "External
  Database URL" do Render) além de `postgresql://` — antes só o formato longo era tratado.
- **Confirmado visualmente pelo usuário no dashboard** (`https://operacionalc6.vercel.app/dashboard`):
  R$ 118.429,37 em comissão à vista, 486 linhas de agosto/2026. Também corrigido nesse processo: janela
  padrão de `GET /metrics` (e do dashboard) ampliada de 30 pra 90 dias — 30 dias cortava dado do dia 1
  do mês quando "hoje" já tinha passado pro mês seguinte (mesma causa raiz do problema de datas do
  pipeline, agora também no lado de leitura).

**Ainda não iniciado:**
- `column_mapping` da tile "Qtde por Alçadas" (comissao_avista) — arquivo já baixa certo, só não é
  parseado ainda.
- **Backlog do usuário (lista literal dele, 2026-09-02), na ordem em que foi dada:**
  1. Configurar e validar as informações — **concluído** (validação completa contra produção citada
     acima, 2268 registros, zero erros).
  2. Checagem/proteção contra dado duplicado ou perdido quando rodar mais de uma vez — **já resolvido**
     (ver "proteção contra duplicata/perda de dado" acima, `run_pipeline()` substitui a janela de datas
     em vez de empilhar).
  3. Construir uma visão de dashboard que gere valor e insights (frontend hoje só mostra total + tabela
     bruta — não iniciado).
  4. Mapear os demais relatórios importantes que ainda não baixamos — 6 novos já mapeados nesta sessão;
     seguir mapeando outros cards do hub "One Page - Auto" fora da aba "Auto" se o usuário pedir mais.

**Dashboard de comissão de GN (`base_final`) — EM ANDAMENTO (2026-09-03):**
Item 3 do backlog acima. O usuário mantém hoje toda a operação numa planilha ("Construcao.xlsx")
com abas `db_*` (algumas já vêm do Looker — já cobertas pelo RPA; outras são cadastro manual) e
`config_*` (tabelas de referência mantidas na mão). A aba `base_final` é o motor de cálculo: uma
linha por contrato, cruzando o dado do Looker com os cadastros pra calcular a **comissão interna do
GN** (Gerente de Negócios — diferente da comissão que o C6 paga pra EHS, que já rastreamos). Plano
completo negociado com o usuário, em 3 fases:
1. **Fase 1 (feita)**: tabelas de cadastro/config no Postgres + endpoint de upload pra atualizações
   futuras — ver abaixo.
2. **Fase 2 (feita)**: serviço que recalcula o equivalente de `base_final` por área/ano/mês — ver
   abaixo.
3. **Fase 3 (implementada, falta validação visual do usuário)**: tela `DashAreaGN` no frontend
   (seletor de área/ano/mês, lojas com produção real vs mercado/potencial) — ver abaixo.

Decisões já tomadas com o usuário (não redecidir):
- Tabelas de config mantidas via **upload de CSV/XLSX** por enquanto (não telas de admin) — usuário
  escolheu "começar com upload, migrar depois".
- Aba `db_Acordos` (metas de % Acordo por loja) **fora de escopo por enquanto** — não é Looker nem
  cadastro já modelado; deixada de fora até o usuário pedir.
- `config_carteira` (identidade comercial da loja por CNPJ) e `db_carterizacao` (histórico de
  área/GN por mês) são cadastros DIFERENTES, confirmado pelo usuário — não são duplicata.

**Fase 1 implementada:** 6 tabelas novas (`app/models/`): `store_registry_monthly` (db_carterizacao),
`store_commercial_terms` (config_carteira), `gn_assignments` (config_GNs), `commission_rate_tiers`
(config_remuneracao), `alcada_discount_rules` (config_regras_alcada), `contract_overrides`
(config_AjustesContrato — só as 2 colunas de entrada manual real, o resto da aba original são
fórmulas derivadas). Migration `0002_config_tables`. Lógica de importação em
`app/services/config_import.py` (substitui a tabela inteira a cada carga, mesmo padrão idempotente
do pipeline de métricas). Endpoints em `app/api/routes/config_data.py`
(`GET /config-data/status`, `POST /config-data/{table}/upload`, admin-only, audit-logado).

**Carga inicial CONCLUÍDA contra produção (2026-09-03)** 🎉: `python -m app.seed_config` rodado com
sucesso contra o Postgres de produção — 4005 `store_registry_monthly`, 522 `store_commercial_terms`,
108 `gn_assignments`, 45 `commission_rate_tiers`, 9 `alcada_discount_rules`, 439 `contract_overrides`.
Dois bugs reais encontrados e corrigidos nas duas primeiras tentativas (ver abaixo) — nenhum na
terceira. Fase 1 completa. Reimportar no futuro: `python -m app.seed_config /caminho/para/Construcao.xlsx`
(substitui cada tabela por inteiro) ou `POST /config-data/{table}/upload`.

**Fase 2 implementada (2026-09-03):** `app/services/gn_dashboard.py` (`get_area_scorecard`,
`list_areas`), exposto em `app/api/routes/gn_dashboard.py`
(`GET /gn-dashboard/areas?ano=&mes=`, `GET /gn-dashboard/area-scorecard?area=&ano=&mes=`,
qualquer usuário autenticado). Antes de escrever o código, reli as fórmulas do `base_final` DIRETO da
planilha (não de memória) pra não embutir um mapeamento errado — descobri que os indicadores que o
`DashAreaGN` realmente usa (contratos, produção, mercado, share) dependem de MENOS coisa do que
parecia: nenhum RPA novo foi necessário, só o fix do "Cd Contrato" já feito antes. Duas decisões
deliberadas em relação à planilha original, ambas documentadas em detalhe no docstring do módulo
(não redecidir sem reler):
1. Área da loja = `StoreRegistryMonthly.carterizacao_ehs` direto (confirmado com o usuário) — a
   coluna `AREA_LOJA_EHS` do `base_final` original tem uma inconsistência real de fórmula (parece
   copy-paste da fórmula vizinha `AREA_LOJA_C6` sem ajustar o valor primário).
2. Metas (META QTD CONTRATO, META SHARE, PRODUÇÃO META POTENCIAL) ficaram de fora desta primeira
   versão — fórmulas originais ambíguas/com filtro de ano hardcoded (usuário concordou, escopo é só
   "números de negócio": contratos, produção, mercado potencial, share).

Indicadores implementados por loja: `qtd_contratos_mes` (comissao_avista, CNPJ extraído do campo
"Lojista" via regex — testado contra dado real, mais robusto que o `RIGHT(LEFT(...))` posicional da
planilha original), `producao_mes` (digitacao_analitico, join por "Cd Contrato"), `mercado_potencial_
media_3m` (painel_visita_mercado, "Financiamento Público Alvo", média móvel real dos últimos 3 meses
fechados — não o filtro hardcoded 2026/mês>=6 da planilha), `mercado_producao_c6_mes`,
`mercado_financiamento_total_mes`, `share_mes` (produção C6 / financiamento total do mercado, calculado
na hora).

**Testado contra produção (2026-09-03)** — dois bugs reais encontrados e corrigidos:
1. **`CNPJ Loja` vem como NÚMERO no JSONB** (pandas infere `int64` de uma coluna 100% numérica),
   não string — comparar contra `StoreRegistryMonthly.cnpj_loja` (sempre string) falhava
   silenciosamente pra TODO cruzamento de mercado (todo campo `mercado_*`/`share_mes` voltava
   `None`, sem erro nenhum). Corrigido com `_norm_cnpj()` em `gn_dashboard.py`, aplicado em todo
   lugar que lê CNPJ de `dimensions`. Documentado como lição geral em `rpa-conventions` item 21
   (qualquer coluna 100%-numérica do Looker pode ter esse mesmo problema).
2. **Risco real de perda de dado histórico** (o item 2 do backlog do usuário, "não perder dado"):
   `run_pipeline()` apagava/reinseria uma janela ÚNICA de 90 dias pra TODA a fonte antes de
   gravar o lote novo. Relatórios com filtro relativo (a maioria) sempre re-buscam a janela
   inteira, então tudo bem — mas `painel_visita_mercado` só consegue retornar o MÊS CORRENTE
   (filtro fixo do Looker, ver `rpa-conventions`). Assim que o calendário virasse de mês, a
   rodada seguinte apagaria o mês anterior (dentro dos 90 dias) sem re-buscar nada pra
   substituir — perda permanente, nunca mais recuperável. Ainda não tinha acontecido de verdade
   (só um mês de histórico existia até agora) mas era um efeito colateral inevitável. Corrigido em
   `app/services/pipeline.py`: a janela de apagar agora é calculada POR `metric_name`, a partir do
   [menor, maior] `metric_date` que aquele metric_name efetivamente trouxe NESTA rodada — não do
   `[date_from, date_to]` pedido. Preserva meses antigos de relatórios "de mês fixo" intactos, sem
   mudar o comportamento dos relatórios que já retornam a janela inteira todo run.

O fix do CNPJ é só do lado de LEITURA (`gn_dashboard.py` normaliza ao ler `dimensions`) — não precisa
rodar o pipeline de novo, o dado já ingerido em setembro/2026 deve funcionar direto com o `git pull`.

Mais dois bugs reais encontrados testando o endpoint de verdade (mesmo dia):
3. **`painel_visita_mercado` voltava CSV vazio** pedindo o mês corrente (Looker ainda não tinha
   calculado esse relatório pros primeiros dias do mês) — corrigido com o placeholder
   `{last_closed_month}` no RPA (ver `rpa-conventions` item 22). Consequência pro serviço: os
   campos de mercado NUNCA vão ser do mês exatamente pedido, sempre um mês (ou mais) atrás —
   `get_area_scorecard` usa o mês mais recente disponível por loja em vez de exigir
   correspondência exata, devolvendo o mês real em `mercado_mes_referencia`. Campos renomeados
   de `mercado_producao_c6_mes`/`mercado_financiamento_total_mes`/`share_mes` para
   `mercado_producao_c6_mes_referencia`/`mercado_financiamento_total_mes_referencia`/
   `share_mes_referencia` pra deixar isso explícito na API.
4. **Números abreviados do Looker** (`"151.9 mil"`, `"1.6 MM"`) quebravam o parsing — tanto na
   coluna de valor quanto numa coluna que ficou só como dimensão (`Financiamento Público Alvo`).
   Lógica de parsing extraída pra `parse_looker_number()` em `app/services/connectors/base.py`,
   compartilhada entre o RPA e o `gn_dashboard.py` (ver `rpa-conventions` item 23).

**VALIDADO pelo usuário contra produção (2026-09-03)** 🎉: `get_area_scorecard(area='CONC BH 5 - P',
ano=2026, mes=9)` — usuário conferiu os números de mercado e confirmaram "correto". Fase 2 completa.

Uma característica dos dados (não bug) descoberta nessa validação: **`qtd_contratos_mes`/
`producao_mes` refletem contrato com comissão JÁ APURADA pelo C6** (fonte `comissao_avista`), não
"toda proposta paga no mês" — durante o mês corrente sempre vem sub-representado, porque a apuração
tem atraso. Confirmado com dado real: loja WAMBERG tinha 2 propostas PAGAS em setembro
(`digitacao_analitico`, quase em tempo real) mas só 1 já apurada em `comissao_avista`. **Decisão
confirmada com o usuário: manter `comissao_avista`** como fonte (mesmo critério da planilha
original) — não trocar para `digitacao_analitico` sem pedido explícito. Documentado em detalhe no
docstring de `gn_dashboard.py`.

**Fase 3 implementada (2026-09-03)**: rota `frontend/src/app/dashboard/gn/page.tsx` — seletor de
área/mês/ano, cards de resumo (lojas na área, com contrato no mês, produção total) e tabela por loja
(contratos, produção, mercado potencial média 3m, share — com o mês de referência real do dado de
mercado exibido no cabeçalho da coluna quando difere do mês pedido). Consome
`fetchGnAreas`/`fetchGnAreaScorecard` (`frontend/src/lib/api.ts`), tipos em `frontend/src/lib/types.ts`.
Link recíproco entre `/dashboard` e `/dashboard/gn`. `next build` e `eslint` limpos — a regra nova
`react-hooks/set-state-in-effect` (vem por padrão no Next 16) foi suprimida de propósito nos dois
efeitos de fetch-on-param-change (mesmo padrão do exemplo oficial de "fetching data" do react.dev,
mais rígida que essa recomendação; justificativa no topo do arquivo). **Ainda não testado num
navegador de verdade** — login exige Google OAuth real, sem acesso a partir do ambiente de
desenvolvimento; falta o usuário abrir `/dashboard/gn` depois do deploy no Vercel e confirmar
visualmente.

**Feedback do usuário (2026-09-04) — números errados + pivô de escopo:** ao testar `/dashboard/gn`
de verdade, o usuário reportou números muito abaixo do esperado (ex.: produção da área "MG 1 CURVELO -
P" mostrando R$ 200 mil contra R$ 1,75 milhão esperado, 10 lojas "com contrato" contra 41 esperado) e
pediu pra focar em construir a **`base_final` completa** (réplica linha-a-linha, todas as ~54 colunas
do Excel, incluindo o cálculo de comissão de GN) em vez de continuar debugando o resumo agregado — pra
ele conseguir fazer os checks direto contra a planilha. Ainda não investigamos a causa da discrepância
do resumo agregado (pode ser o mesmo lag de apuração do `comissao_avista` já documentado, agravado, ou
outra coisa — não sabemos ainda, ficou pra depois).

**`base_final` completa implementada (2026-09-04):** `app/services/base_final.py`
(`get_base_final_rows`), exposta em `GET /gn-dashboard/base-final?ano=&mes=&area=` (área opcional).
Réplica FIEL da fórmula original coluna por coluna — inclusive a inconsistência conhecida de
`AREA_LOJA_EHS` (ver módulo `gn_dashboard.py`) e o provável nome trocado de `COMISSAO_SEGUROS_R$`
(puxa de "R$ Comissão Produto - Parceiro", não "Seguros") — documentadas no docstring do módulo,
NÃO corrigidas, porque o objetivo aqui é comparação célula a célula com o Excel do usuário.

Pré-requisito novo (RPA): `comissao_avista`'s tile "Analítico" teve `dimension_columns` ampliado pra
cobrir TODAS as colunas de `db_apuracaoavista` (antes só tinha as básicas de identificação) — sem
isso os campos de comissão/alçada/flags de `base_final` vêm todos `None`. `producao_por_filial`
(dentro de `apuracao_parceiro_resumo`) ganhou `% Ating. Ponderado Ajustado` (é o `FATOR_META`).
**Precisa rodar o pipeline de novo** antes de `base-final` ter dado completo — testado o parsing
contra os arquivos reais (486 registros de comissao_avista, 71 de producao_por_filial, sem descarte),
mas não contra produção ainda.

Descoberto no processo (`rpa-conventions` itens 24-25): a coluna "Filial" desse relatório de metas
vem com prefixo de código (`"28151 - CONC BH 4 - P"`), diferente do formato usado como chave de área
em todo o resto (sem código) — tratado com `_strip_filial_code`. E campos monetários/percentuais que
ficam só como dimensão (nunca viram `value`) vêm como texto formatado do Looker igual às colunas de
valor — usar `parse_looker_number`/parse manual de `%`, nunca `float()` direto.

**Frontend implementado (2026-09-04)**: `frontend/src/app/dashboard/base-final/page.tsx` — uma linha
por contrato, ~50 colunas, cabeçalho agrupado de 2 linhas (igual à planilha: Data, Loja, Contrato, Vl
Financ., Vl Seguro, Comissão EHS, Taxa, Comissão GN, IDs), filtro de texto por coluna + ordenação por
clique no cabeçalho, tudo client-side. `next build`/`eslint` limpos. Navegação entre as 3 telas
(`/dashboard`, `/dashboard/gn`, `/dashboard/base-final`). **Ainda não testado contra produção nem num
navegador de verdade** — depende do usuário rodar o pipeline de novo (pré-requisito de RPA acima) e
depois abrir a tela pra validar visualmente contra o Excel.

**Bug real na primeira tentativa de carga (2026-09-03)**: `psycopg.errors.NumericValueOutOfRange` em
`store_registry_monthly.mercado` — a coluna "Mercado" de `db_carterizacao`/`config_carteira` **não é
percentual** (só assumi isso porque a primeira linha de amostra que olhei tinha 0/vazio, igual
Retorno/Acordo/Comissão Seguros, que ESSES sim são percentuais ≤6%) — é potencial de mercado em R$,
com valores reais de até R$ 40 milhões numa loja. `Numeric(9,6)` estourava. Corrigido pra
`Numeric(18,2)` (mesma precisão de `Metric.value`) em `store_registry_monthly.py` e
`store_commercial_terms.py`, com migration nova `0003_fix_mercado_precision` (a `0002` já tinha rodado
em produção, não dava mais pra editar ela direto). Lição: **antes de fixar a precisão de um campo
numérico novo, checar o range real dos dados** (`df[col].abs().max()`) em vez de inferir pelo valor de
uma linha de amostra só — já vi essa mesma linha em 4 das outras colunas da mesma aba, mas era
coincidência (eram todas 0 nessa loja específica).

**Segundo bug na mesma tentativa**: `UniqueViolation` em `gn_assignments` — a aba `config_GNs` tem 4
linhas duplicadas de verdade (mesma área/ano/mês repetida 2x, ex. "BELO HORIZONTE 13 - P"/2026/9).
Na planilha original isso é inofensivo (XLOOKUP sempre pega só a primeira ocorrência), mas a
constraint `UNIQUE(area, ano, mes)` rejeitava a segunda linha. Corrigido em `import_gn_assignments`:
ignora repetição da mesma chave só se o GN for IGUAL nas duas linhas (mesmo comportamento do XLOOKUP);
se o GN for diferente, é conflito real na fonte — a importação para com `ValueError` explícito em vez
de escolher uma das duas silenciosamente.

**Bug real encontrado ao planejar a Fase 2** (documentado em detalhe em `rpa-conventions` item 20):
`dimension_columns` de `digitacao_analitico` (relatório `acompanhamento_veiculos`) não tinha
`Cd Contrato` — a chave que liga cada proposta de veículo ao contrato de comissão em
`comissao_avista`, essencial pro join de `base_final`. Corrigido em `portal_selectors.json`
(adicionado `Cd Contrato`, `ID Proposta`, `Cd Contrato Inter`). **Requer rodar o pipeline manual de
novo** pra esse campo aparecer nas métricas já ingeridas (os 2268 registros atuais não têm essa
dimensão ainda).

- ~~Configurar o robô pra rodar sozinho DENTRO do Render~~ — **tentado e descartado em 2026-09-01**:
  o Cloudflare do C6 bloqueia ativamente a conexão vinda do datacenter do Render (Oregon/EUA) —
  `"Sorry, you have been blocked"`, confirmado por print de falha real. Não é bug de código, é defesa
  de segurança do portal funcionando como esperado — está dentro da "Linha que não se cruza" (ver
  `rpa-conventions`, item 15), não vamos contornar. SSH + disco persistente + perfil de navegador
  copiado (tudo isso já foi feito e funciona tecnicamente) ficam documentados como referência, mas a
  execução dentro do Render em si não é viável enquanto o C6 não confiar nessa origem. Próximo passo
  real: rodar o agendamento a partir da rede do usuário (Agendador de Tarefas do Windows), ou pedir ao
  C6 pra liberar a origem formalmente.
~~Pendência de correção "hoje até hoje" no pipeline~~ — corrigida em 2026-09-01, junto com um segundo
bug mais sério achado na hora de preparar o agendamento automático: **nenhuma proteção contra
duplicata**. `run_pipeline()` só fazia `INSERT`, nunca substituía nada — como o agendador roda 3x/dia,
ia empilhar os mesmos registros pra sempre. Corrigido em `app/services/pipeline.py`:
1. Default de `date_from` mudou de "mesmo dia que `date_to`" pra "90 dias antes" (mesmo raciocínio do
   fix do `/metrics`).
2. Antes de inserir os registros buscados, a rodada agora **apaga** as métricas já existentes daquela
   `source` dentro da janela `[date_from, date_to]` e insere as novas por cima — cada execução
   substitui a janela inteira em vez de empilhar. Preserva dado de fora da janela e de outras fontes;
   idempotente rodar quantas vezes quiser.
- Confirmação formal com o C6 de que a automação é sancionada (ver `rpa-conventions` — o portal reage
  diferente a navegador automatizado; ainda não temos essa confirmação do banco)

~~Criar o OAuth Client do Google~~ — feito em 2026-08-27. `GOOGLE_OAUTH_CLIENT_ID` =
`1038135927680-3tvpk42jdnk1v3ab84rsfciqlbnelsdo.apps.googleusercontent.com` (não é segredo). Authorized
JavaScript origins já inclui `https://operacionalc6.vercel.app` (feito em 2026-09-01, ver detalhes
abaixo).

**Feito (infra/organização, 2026-08-18):**
- Organização `OperacionalC6` criada no GitHub e repositório transferido pra lá (app do Claude reinstalado
  lá — precisou reinstalar porque o app não segue automaticamente a transferência de dono)
- Conta da Render criada (login GitHub, plano pago, cartão da empresa cadastrado) — nenhum serviço
  configurado ainda, só a conta
- Conta da Vercel criada (login com Google; GitHub conectado depois via "Login Connections", dando acesso
  à organização `OperacionalC6`) — plano gratuito (Hobby)

**Feito (backend pronto pra deploy, 2026-08-27):**
- Login trocado de senha própria pra Google Sign-In (`POST /auth/google`) — ver skill `security-access`
  pra detalhes de implementação
- `render.yaml` (Blueprint) criado na raiz do repo — declara o serviço web (Docker, disco persistente
  pro perfil do RPA) e o Postgres
- `backend/entrypoint.sh` criado — roda `alembic upgrade head` + `python -m app.seed` antes de subir o
  uvicorn, necessário porque é um serviço gerenciado (ninguém vai digitar esses comandos manualmente)
- Corrigida dependência faltante (`pydantic[email]`) que impedia o backend de subir
- Migração inicial (`0001_init`) ajustada pra remover campos de senha (nunca foi rodada contra um banco
  real, então editei direto em vez de empilhar migração nova — não fazer isso depois que a coluna tiver
  rodado em produção de verdade)

**Feito (backend NO AR em produção, 2026-08-31):** 🎉
- Blueprint conectado no Render, banco Postgres + serviço web rodando de verdade em
  `https://operacionalc6-backend.onrender.com`
- Três bugs reais só descobertos rodando contra o Render de verdade (nenhum tinha sido testado contra
  Postgres real até então) — todos corrigidos, documentados em detalhe como lições pra próxima vez que
  alguém mexer nesses arquivos:
  1. **Driver do Postgres**: a connection string do Render vem sem driver explícito
     (`postgresql://...`), SQLAlchemy assume psycopg2 (não instalado, usamos psycopg3) — corrigido com
     um `field_validator` em `Settings.database_url` (`app/core/config.py`) que força
     `postgresql+psycopg://` sempre, não importa a origem da URL.
  2. **Migration não idempotente**: `0001_init.py` chamava `enum.create(checkfirst=True)` E DEPOIS usava
     o mesmo enum numa coluna (`create_table` também cria o tipo) — na prática funciona uma vez, mas se a
     migration falhar no meio (aconteceu por causa do bug #1) e for reexecutada, quebra com "type already
     exists". Removidas as chamadas `.create()` redundantes.
  3. **Enums do SQLAlchemy mandando o nome errado**: por padrão SQLAlchemy manda o NOME do membro Python
     do Enum (`"ADMIN"`) pro Postgres em vez do VALUE (`"admin"`) — mesmo em Enums com mixin de `str`.
     A migration criou o tipo com valores minúsculos, então todo INSERT/UPDATE que usasse
     `User.role`/`PipelineRun.status`/`PipelineRun.trigger` ia quebrar. Corrigido com
     `values_callable=lambda cls: [e.value for e in cls]` nas três colunas enum.
- **Se o banco ficar num estado quebrado de novo** (ex.: tipo enum criado mas tabela não): como não tem
  dado real ainda, o caminho mais simples é apagar o banco (`operacionalc6-db`, NÃO o web service) no
  Render e rodar "Manual Sync" no Blueprint pra recriar do zero — não precisa mexer em SQL manualmente.
- **Confirmado pelo usuário, funcionando de ponta a ponta**: `GET /health` → `{"status":"ok"}` e `GET /docs`
  mostrando o Swagger UI completo ("Operacional C6 — API", OAS 3.1) com as rotas de `auth`, `teams` e
  `users`. Backend considerado 100% pronto pra produção — próximo marco é o frontend.

## Frontend mínimo (Task #5)

**Feito (código, 2026-08-31):** scaffold do Next.js criado em `frontend/` (App Router, TypeScript,
Tailwind). Build e lint passam. Duas páginas:
- `/` (`frontend/src/app/page.tsx`): tela de login com o botão do Google Identity Services
  (script `accounts.google.com/gsi/client`); ao autenticar, chama `POST /auth/google` e guarda os
  tokens.
- `/dashboard` (`frontend/src/app/dashboard/page.tsx`): busca `GET /auth/me` + `GET /metrics` e
  mostra total do período + tabela. Redireciona pra `/` se não houver token.
- `frontend/src/lib/api.ts`: client fetch com renovação automática via `POST /auth/refresh` em
  qualquer 401.
- Tokens guardados em `localStorage` (tradeoff aceito pra essa fase — se algum dia entrar script de
  terceiro no frontend, migrar pra cookie httpOnly setado pelo backend).
- Variáveis de ambiente do frontend (ver `frontend/.env.local.example`): `NEXT_PUBLIC_API_URL` e
  `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (mesmo Client ID do backend, não é segredo).

**Feito (frontend NO AR em produção, 2026-09-01):** 🎉
- Publicado na Vercel: `https://operacionalc6.vercel.app` (branch de produção configurada como
  `claude/previous-session-recovery-fv67s4`, Root Directory `frontend`, Framework Preset `Next.js`).
- `https://operacionalc6.vercel.app` liberado em "Authorized JavaScript origins" do OAuth Client no
  Google Cloud Console.
- `BACKEND_CORS_ORIGINS` no Render atualizado pra incluir essa URL.
- **Login com Google + dashboard validados de ponta a ponta pelo próprio usuário**, contra o backend
  e banco de produção reais. Walking skeleton completo (backend + frontend + auth) confirmado
  funcionando.
- Armadilhas do primeiro deploy na Vercel, documentadas pra não perder tempo de novo:
  1. **Repositório tinha uma branch "default" diferente de `main`** (`claude/c6bank-reports-automation-5391mz`,
     de uma sessão antiga) — a Vercel usa a branch default do GitHub pra popular a lista de pastas no
     import, então `frontend/` não aparecia. Corrigido em Settings → Environments → Production →
     Branch Tracking, apontando pra `claude/previous-session-recovery-fv67s4`.
  2. **"Redeploy" de um deployment antigo reusa o commit/branch ORIGINAL daquele deployment**, não a
     configuração atual do projeto — não adianta mudar Branch Tracking e clicar "Redeploy" num
     deployment criado antes da mudança. É preciso um push novo (ou "Create Deployment" apontando a
     branch certa) pra gerar um deployment que já nasce com a config nova.
  3. **Root Directory** nessa versão da Vercel fica em Settings → **Build and Deployment** (não em
     "General" nem em "Git").
  4. **Framework Preset ficou preso em "Other"**: foi detectado errado durante o import inicial
     (quando a Root Directory ainda apontava pra raiz do repo, sem `package.json`). Trocar a Root
     Directory depois não corrige o preset sozinho — precisa ir em Build and Deployment e trocar
     manualmente pra "Next.js", senão o build "passa" mas todas as rotas retornam 404.
  5. **As env vars `NEXT_PUBLIC_*` não foram salvas no primeiro import** (pulamos aquela tela ao
     corrigir a Root Directory) — sem elas o Google Identity Services dá erro
     `Missing required parameter: client_id`. `NEXT_PUBLIC_*` é "assado" no build, então precisa de
     um redeploy novo depois de cadastrar.
  6. **Erro "origin_mismatch" do Google**: cada deployment da Vercel gera uma URL única
     (`operacionalc6-xxxxx-operacional-c6.vercel.app`) — o Google só aceita login na origem
     cadastrada (`https://operacionalc6.vercel.app`, o domínio de produção estável). Testar sempre
     nesse domínio, não na URL de um deployment específico.
- **Pendente de limpeza (não bloqueia nada)**: o projeto da Vercel importou automaticamente ~26
  variáveis de ambiente do `.env.example` da raiz do repo (`POSTGRES_*`, `DATABASE_URL`,
  `JWT_SECRET_KEY` etc.) — são do backend, o frontend não usa nenhuma. Vale remover em Settings →
  Environment Variables pra não expor detalhes de infra do backend num projeto que não precisa
  deles.

## Como uma sessão nova deve retomar

1. Ler esta skill primeiro.
2. Rodar `git log --oneline -20` no branch de trabalho pra ver o que mudou desde a última vez.
3. Se for mexer no RPA, ler a skill `rpa-conventions` antes de tocar em `portal_rpa.py`/`portal_selectors.json`.
4. Se for mexer em auth/acesso/segredos, ler a skill `security-access` antes.
5. Atualizar esta skill (seção "Status atual") sempre que fechar um marco importante — não deixar ela
   ficar desatualizada, é o principal jeito de uma sessão futura não perder contexto.
