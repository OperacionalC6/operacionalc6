---
name: security-access
description: Regras de segurança, controle de acesso (RBAC) e tratamento de segredos do projeto operacionalc6. Consulte SEMPRE antes de implementar login/autenticação, antes de criar ou configurar contas de nuvem/hospedagem, antes de decidir quem pode ver quais dados, e antes de commitar ou logar qualquer coisa que possa ser credencial. Também consulte se o usuário colar uma senha/token no chat por engano.
---

# Segurança e controle de acesso — operacionalc6

## Requisito de negócio (não negociável)

O painel é uso interno: só o dono do negócio e seus consultores autorizados podem ver os dados —
nenhum acesso externo/público. Isso guia toda decisão de auth abaixo.

## Autenticação decidida

A empresa **não tem domínio corporativo** (usa Gmail pessoal — ver skill `project-context`), então não
dá pra restringir login por domínio Google Workspace. Decisão: **login via Google + lista de e-mails
autorizados** mantida pelo admin dentro do próprio sistema (usa o RBAC já modelado em
`backend/app/models/user.py`). Nunca aceitar cadastro público/self-service — toda conta é criada/convidada
por um admin.

Se a empresa adquirir domínio próprio + Google Workspace no futuro, revisitar para restrição por domínio
(`hd` parameter no OAuth) como camada extra — mas a lista de e-mails autorizados continua sendo a
autorização de fato, não o domínio.

## RBAC (já modelado no backend)

Dois níveis, ver `backend/app/models/user.py`, `team.py` e `backend/app/api/deps.py`:
- **admin/gestor**: vê todos os dados, todas as equipes.
- **membro**: escopado pela(s) equipe(s) associada(s) — só vê o que é da sua equipe.

Qualquer view/endpoint novo precisa checar o escopo do usuário logado antes de retornar dados — nunca
confiar em filtro feito só no frontend (o frontend é conveniência de UX, a autorização real é no backend).

## Segredos e credenciais

- Credenciais reais (usuário/senha do WebAutorizador, futuras chaves de API) **nunca** vão pro git.
  Vivem em `.env` local (não versionado, `.gitignore` já cobre) ou no gerenciador de segredos da
  plataforma de hospedagem quando formos pra produção (variáveis de ambiente do Render, não arquivo).
- `browser_profile/` (perfil do navegador do RPA, tem cookies de sessão reais) e `artifacts/`
  (screenshots/HTML de falha, podem conter dados sensíveis) também nunca vão pro git — já cobertos
  no `.gitignore`.
- Se o usuário colar uma senha/token no chat por engano: não repita o valor de volta, oriente a
  trocar a credencial imediatamente (uma vez enviada numa conversa, trata como exposta), e explique
  onde a credencial deveria ter ido em vez disso.
- O usuário de automação do RPA deve ser um usuário dedicado solicitado ao C6 (não a conta pessoal de
  ninguém) — já documentado no cabeçalho de `portal_rpa.py`; reforçar isso quando ajudar a configurar
  produção.

## Contas de infraestrutura

Toda conta de nuvem/hospedagem (Render, Vercel, futuros provedores) deve ser criada com e-mail da
empresa e, quando possível, cartão/CNPJ da empresa — nunca a conta pessoal do usuário, e nunca rodando
na máquina pessoal dele em produção (isso já foi pedido explicitamente). Rodar localmente na máquina do
usuário vale só para desenvolvimento/teste, nunca para o serviço em produção que os consultores acessam.

## Log de auditoria

O modelo `backend/app/models/audit_log.py` já existe para registrar ações sensíveis (login, exportação
de dados, mudanças de permissão). Ao implementar rotas novas que leem/exportam dados financeiros,
verificar se a ação deveria gerar um registro de auditoria — dado que é informação de comissão/produção
de parceiros externos, é razoável querer saber quem acessou o quê e quando.

## Dados sensíveis nos relatórios em si

Os CSVs extraídos do Looker contêm CNPJ, nomes de lojistas/parceiros e valores financeiros reais. Tratar
como dado de negócio confidencial: não colar esses dados em lugares públicos, não anexar sem necessidade
em canais não autorizados. Isso vale também para os prints/artefatos de debug do RPA.
