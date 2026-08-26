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

- **Backend**: FastAPI + Postgres, já escrito em `backend/app/`. Login JWT, RBAC (admin/gestor veem tudo,
  membro só vê sua equipe — ver `security-access` skill), log de auditoria, camada de conectores plugável
  (`DataConnector`: RPA hoje, API oficial do C6 como stub pra quando/se sair homologação).
- **Frontend**: ainda não existe. Decidido: Next.js, hospedado na Vercel, **plano gratuito (Hobby)** —
  sem desvantagem prática pra esse projeto, migrar pra Pro é só questão de billing, não bloqueia nada.
- **Hospedagem backend+worker RPA+Postgres**: Render, **plano PAGO desde o início** (decisão do usuário
  em 2026-08-18 — preferiu simplicidade de um provedor só a economizar rodando o robô localmente/banco
  temporário). Isso evita: soninho do plano grátis no backend, expiração do Postgres grátis, e a
  necessidade de manter o robô do RPA rodando na máquina do usuário — ele já pode morar no Render desde
  o começo, com disco persistente pro perfil do navegador (ver `rpa-conventions`).
- **Domínio**: a empresa NÃO tem domínio próprio (usa Gmail pessoal). Decidido usar os subdomínios
  gratuitos do Render/Vercel por enquanto — domínio próprio é opcional, adicionar depois se quiser.
- **Autenticação**: login via Google + lista de e-mails autorizados mantida pelo admin (não dá pra restringir
  por domínio Google Workspace porque não existe domínio corporativo — se a empresa adquirir um domínio/
  Workspace no futuro, revisitar essa decisão).
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
- Criação das contas de nuvem da empresa (Render pago, Vercel grátis) — em andamento em 2026-08-18
- Deploy de qualquer coisa em produção
- Confirmação formal com o C6 de que a automação é sancionada (ver `rpa-conventions` — o portal reage
  diferente a navegador automatizado; ainda não temos essa confirmação do banco)

**Feito (infra/organização, 2026-08-18):**
- Organização `OperacionalC6` criada no GitHub e repositório transferido pra lá

## Como uma sessão nova deve retomar

1. Ler esta skill primeiro.
2. Rodar `git log --oneline -20` no branch de trabalho pra ver o que mudou desde a última vez.
3. Se for mexer no RPA, ler a skill `rpa-conventions` antes de tocar em `portal_rpa.py`/`portal_selectors.json`.
4. Se for mexer em auth/acesso/segredos, ler a skill `security-access` antes.
5. Atualizar esta skill (seção "Status atual") sempre que fechar um marco importante — não deixar ela
   ficar desatualizada, é o principal jeito de uma sessão futura não perder contexto.
