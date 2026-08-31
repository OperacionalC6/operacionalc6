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

## Status atual (2026-08-18)

**Funcionando e validado contra o portal real:**
- Login no WebAutorizador (`backend/app/services/connectors/portal_rpa.py`)
- Acesso aos dashboards Looker (via bootstrap — ver skill `rpa-conventions`)
- Download das 4 tiles do relatório "Apuração Comissão À Vista" (dashboard Looker `corp_consignado_embed::01526_auto`)
- Parsing completo de 1 das 4 tiles ("Analítico") → 214 registros normalizados por execução

**Pendente dentro do mesmo relatório:**
- `column_mapping` das tiles "Detalhamento", "Detalhamento por Filial" e "Qtde por Alçadas" (arquivos já
  baixam certo, só não são parseados ainda — ver `portal_selectors.json`)

**Ainda não iniciado:**
- Mapear os outros relatórios do hub "One Page - Auto" (ex.: Apuração Comissão Carteira, Apuração Parceiro
  - Histórica, Resumo Apuração Parceiro 2.0, Painel Visita - Mercado, e outros cards fora da aba "Auto")
- Frontend (não existe nenhuma linha ainda)
- ~~Criar o OAuth Client do Google~~ — feito em 2026-08-27. `GOOGLE_OAUTH_CLIENT_ID` =
  `1038135927680-3tvpk42jdnk1v3ab84rsfciqlbnelsdo.apps.googleusercontent.com` (não é segredo, pode
  usar direto no backend e no frontend). "Authorized JavaScript origins" hoje só tem
  `http://localhost:3000` — precisa voltar lá e adicionar a URL de verdade da Vercel assim que o
  frontend for publicado.
- Conectar o `render.yaml` no dashboard do Render (Blueprint) e preencher as variáveis marcadas
  `sync: false` (segredos) — arquivo já existe no repo, só falta rodar o deploy de fato
- Importar/publicar o projeto na Vercel — conta e conexão com o GitHub prontas, mas sem frontend pra
  publicar ainda
- Confirmação formal com o C6 de que a automação é sancionada (ver `rpa-conventions` — o portal reage
  diferente a navegador automatizado; ainda não temos essa confirmação do banco)

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

## Como uma sessão nova deve retomar

1. Ler esta skill primeiro.
2. Rodar `git log --oneline -20` no branch de trabalho pra ver o que mudou desde a última vez.
3. Se for mexer no RPA, ler a skill `rpa-conventions` antes de tocar em `portal_rpa.py`/`portal_selectors.json`.
4. Se for mexer em auth/acesso/segredos, ler a skill `security-access` antes.
5. Atualizar esta skill (seção "Status atual") sempre que fechar um marco importante — não deixar ela
   ficar desatualizada, é o principal jeito de uma sessão futura não perder contexto.
