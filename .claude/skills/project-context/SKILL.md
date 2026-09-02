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

## Status atual (2026-09-02)

**Funcionando e validado contra o portal real:**
- Login no WebAutorizador (`backend/app/services/connectors/portal_rpa.py`)
- Acesso aos dashboards Looker (via bootstrap — ver skill `rpa-conventions`)
- **3 relatórios Looker mapeados e validados** (todos com dados reais fornecidos pelo usuário, não
  seletores adivinhados — ver `portal_selectors.json`):
  1. `comissao_avista` (dashboard `corp_consignado_embed::01526_auto`) — 4 tiles, 3 mapeadas
     (`comissao_avista`, `comissao_avista_detalhamento`, `comissao_avista_por_filial`); "Qtde por
     Alçadas" deixada pra depois (cabeçalho pivotado, precisa parsing especial).
  2. `apuracao_parceiro_resumo` (dashboard `corp_consignado_embed::01532_auto`) — 4 tiles, todas
     mapeadas: `comissao_liquida`, `comissao_carteira`, `producao`/`producao_por_filial`,
     `seguros`/`seguros_por_filial`.
  3. `acompanhamento_veiculos` (dashboard `corp_consignado_embed::00087`) — 1 tile mapeada
     (`digitacao_analitico`, dado por proposta individual, não apuração mensal). Abas "Digitação" e
     "Produção" do mesmo dashboard ainda não mapeadas.
- **9 métricas distintas no total.** Convenção importante (ver `rpa-conventions` itens 16-17): quando
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
- 486 registros reais gravados em produção (Postgres do Render), confirmados no dashboard.

**Pendente dentro dos relatórios já mapeados:**
- `column_mapping` da tile "Qtde por Alçadas" (comissao_avista) — arquivo já baixa certo, só não é
  parseado ainda (ver `portal_selectors.json`).
- Abas "Digitação" e "Produção" do dashboard `acompanhamento_veiculos` (só "Analítico" mapeada até
  agora).

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
- Mapear os outros relatórios do hub "One Page - Auto" (ex.: Apuração Comissão Carteira, Apuração Parceiro
  - Histórica, Resumo Apuração Parceiro 2.0, Painel Visita - Mercado, e outros cards fora da aba "Auto")
- `column_mapping` das 3 tiles restantes do relatório já mapeado ("Detalhamento", "Detalhamento por
  Filial", "Qtde por Alçadas") — arquivos já baixam certo, só não são parseados ainda.
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
