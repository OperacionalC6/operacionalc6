---
name: rpa-conventions
description: Convenções e lições aprendidas (na marra, testando contra o portal real) sobre o conector RPA do C6 Consig (backend/app/services/connectors/portal_rpa.py e portal_selectors.json) — Playwright, login WebAutorizador, dashboards Looker embutidos, parsing de CSV. Consulte SEMPRE antes de editar esses dois arquivos, antes de propor uma forma de esperar/clicar/navegar num teste RPA, ou ao diagnosticar um novo erro do script (timeout, TargetClosedError, popup inesperado). Evita redescobrir os mesmos problemas (perfil de navegador, popups, seletores) do zero.
---

# Convenções do conector RPA (C6 Consig)

## O sistema real (não é só um portal)

Duas coisas distintas, mesma sessão de login:
1. **WebAutorizador** (`c6.c6consig.com.br`) — login ASP.NET WebForms clássico (UpdatePanel/postback).
2. **Looker** (`c6bank.cloud.looker.com`) — onde os relatórios de comissão de verdade ficam (dashboards
   embutidos), acessado a partir de um hub interno "One Page - Auto".

**Importante**: ir direto pra URL de um dashboard Looker sem antes visitar o WebAutorizador em
`bootstrap_path` (`/WebAutorizador/MenuWeb/Relatorios/Documentacao/UI.RelatorioGerencialExterno.aspx`)
resulta em página de "não autorizado" — essa página faz um handshake/SSO com o Looker que autoriza a
sessão do navegador. O código já trata isso em `_bootstrap_looker_session`; se for adicionar um dashboard
Looker novo, não pule esse passo.

## Erros que já resolvemos — não reintroduzir

Cada um destes já causou uma sessão inteira de debug. Se um sintoma parecido aparecer, comece por aqui:

1. **`page.goto(..., wait_until="networkidle")` trava/estoura timeout.**
   O WebAutorizador e o Looker mantêm chamadas de rede em segundo plano (antifraude, analytics,
   polling) que nunca "acalmam". Use `wait_until="domcontentloaded"` e depois espere um elemento
   concreto ficar visível (`locator(...).wait_for(state="visible")`), nunca confie em networkidle.

2. **`TargetClosedError` no meio do login, sem motivo aparente.**
   Quase sempre é o navegador sendo fechado por fora do script (usuário achando que travou, ou um
   popup nativo sem handler). Antes de mexer no código, pergunte: alguém fechou a janela manualmente?
   Apareceu algum popup que não foi respondido?

3. **Popup "Acessar outros apps e serviços neste dispositivo" (permissão nativa do Chrome).**
   É a "Local Network Access" do Chrome — o portal faz alguma checagem local. Resolvido usando
   `launch_persistent_context(RPA_BROWSER_PROFILE_DIR, ...)` em vez de `launch()` + `new_context()`:
   um perfil de navegador novo a cada execução parece um "dispositivo desconhecido" pro portal. Com
   perfil persistente, a aprovação feita uma vez (numa rodada manual com HEADLESS=false) fica salva.
   **Nunca commitar a pasta do perfil** — tem cookies de sessão reais (já no `.gitignore`).

4. **Login trava esperando resposta que nunca chega, mesmo com usuário/senha certos.**
   O WebAutorizador dispara um `confirm()` nativo do navegador quando já existe outra sessão logada
   ("Usuário já autenticado em outra estação..."). Por padrão o Playwright **fecha esse tipo de popup
   sozinho sem executar nada** (equivalente a Cancelar) se não houver um listener registrado. Resolvido
   com `page.on("dialog", lambda dialog: dialog.accept())`, registrado uma vez por página antes do login.

5. **Clicar em "Download data" no Looker não baixa nada (timeout esperando o evento de download).**
   Abre um modal com dropdown de formato (CSV por padrão) e um botão "Download" que precisa ser
   clicado à parte — não baixa direto no primeiro clique.

6. **Botões do Looker identificados por classe CSS quebram a cada deploy.**
   O Looker usa styled-components com hash (`sc-xxxx`) que mudam. Use sempre `aria-label` — é estável.
   Padrão confirmado: cada tile tem um botão `aria-label="{Nome da Tile} - Tile actions"`.

7. **`pd.read_csv(file_path, sep=None, engine="python")` quebra com `ParserError` em CSVs do Looker.**
   O sniffer de separador do engine Python se confunde com valores monetários entre aspas contendo
   vírgula de milhar (`"R$ 653,440.00"`). Use `pd.read_csv(file_path)` simples (engine C, lida com
   aspas corretamente).

8. **Colunas monetárias do Looker vêm como texto, não número.**
   Formato `"R$ 1,234.56"` (vírgula de milhar, ponto decimal — não é o padrão BR de exibição, é o
   locale do Looker). Use `PortalRpaConnector._parse_brl_value()` em vez de `float()` direto.

9. **Colunas de "mês" tipo `Anomes Apuracao` vêm como `202608` (AAAAMM), não uma data.**
   `pd.to_datetime` sem formato explícito não trata bem. Use o campo opcional `date_format` no
   `column_mapping` (ex.: `"%Y%m"`), já suportado em `_parse_report`.

10. **Popup nativo "Salvar senha?" do Chrome interrompe execução sem supervisão.**
    Desativado via `args=["--disable-save-password-bubble"]` no `launch_persistent_context`.

11. **`TimeoutError: Timeout ... exceeded while waiting for event "download"` numa tile específica.**
    Confirmado em teste real contra produção (2026-09-01): a tile "Comissão À Vista - Detalhamento por
    Filial" veio com "No Results" na tela (print de falha salvo automaticamente) — o filtro de período
    configurado (`filter_value: "this month"`) não tinha dado ainda fechado/disponível no momento do
    teste. Trocado pra `"2 months"` (equivalente a "is in the last 2 months" na UI do Looker) pra sempre
    cobrir pelo menos um mês fechado além do corrente. Se aparecer de novo: confirme pelo
    `failure_<timestamp>.png` salvo em `RPA_ARTIFACTS_DIR` se a tile estava vazia ("No Results") — se
    sim, é filtro de período curto demais, não bug de seletor.

12. **Mesmo `TimeoutError` em "waiting for event download", mas agora com a tile CHEIA de dados no print**
    (não mais "No Results") — outra causa possível, ainda sob suspeita (2026-09-01): o botão "Tile
    actions" no header de uma tile fica visível antes da tile terminar de rodar sua própria query —
    então só esperar esse botão (padrão já usado pra tile[0] antes do loop) não garante que uma tile
    mais abaixo/mais pesada já renderizou quando o loop chega nela. Paliativo aplicado: `download_wait_ms`
    de 20000 para 60000 em `portal_selectors.json`. Se voltar a falhar mesmo com 60s, o próximo passo é
    rodar `HEADLESS=false` e achar um seletor confiável de "tile terminou de carregar" (provável
    spinner do Looker) pra esperar por tile, individualmente, antes de cada `expect_download` — não
    escrever esse seletor às cegas, confirmar visualmente primeiro.

13. **`psycopg.errors.InvalidTextRepresentation: invalid input syntax for type json` / `Token "NaN" is invalid`
    ao gravar em `metrics`.**
    Célula vazia numa coluna de dimensão do CSV do Looker (ex.: "Status Contrato" em branco) vira `NaN`
    (float) do pandas, não string vazia. O `json` do Python serializa `NaN` como o token literal `NaN`
    (aceita por padrão, mesmo não sendo JSON válido pela especificação) — mas o parser JSONB do Postgres
    rejeita e quebra o INSERT em lote inteiro por causa de uma linha só. Resolvido convertendo `NaN` pra
    `None` (vira `null` no JSON) ao montar o dict de `dimensions` em `_parse_report`, usando `pd.isna()`.

14. **`Executable doesn't exist at /ms-playwright/.../chrome-headless-shell` só em produção (Render),
    nunca local.**
    `requirements.txt` tinha `playwright>=1.46` (sem travar versão) — a cada rebuild do Docker, o
    `pip install` pega a versão mais nova do PyPI, mas a imagem base (`mcr.microsoft.com/playwright/python:v1.46.0-jammy`)
    só tem os navegadores baixados pra 1.46.0 exatamente. Funcionou "por acaso" no primeiro deploy;
    quebrou depois de vários redeploys pegarem uma versão mais nova. Corrigido travando
    `playwright==1.46.0` (igual à tag da imagem). **Se atualizar a versão do Playwright, atualize os
    dois juntos** (`requirements.txt` e a tag `FROM` do `Dockerfile`) — nunca só um dos dois.

15. **Cloudflare do C6 bloqueia a conexão vinda do Render (`"Sorry, you have been blocked"`,
    `c6consig.com.br`), mesmo com login/senha/perfil aprovado corretos — confirmado em teste real
    (2026-09-01).**
    Não é bug de código — é o Cloudflare do próprio portal recusando a origem (datacenter Render,
    região Oregon/EUA). Confirmado pelo print de falha (`failure_*.png`): tela de bloqueio do
    Cloudflare, não a tela de login. **Isso está DENTRO da "Linha que não se cruza" abaixo — não
    existe fix de código pra isso, e não vamos tentar (trocar IP escondido, VPN, falsificar
    cabeçalhos, etc.).** Conclusão prática: rodar o robô de dentro do Render não é viável como está.
    Duas saídas legítimas: (a) pedir ao C6 pra confiar/liberar essa origem formalmente, junto com a
    confirmação de que a automação é sancionada; (b) rodar o agendamento a partir da rede/máquina do
    usuário (já aceita pelo portal), via Agendador de Tarefas do Windows — não dentro do Render.

16. **Uma tile pode trazer mais de um número que merece virar métrica separada** (ex.: tile "Comissão
    Total" traz À Vista e Carteira na mesma linha; "Bloco de Metas" traz Produção e Seguros).
    `column_mapping` agora aceita uma LISTA de mappings (além do dict único de antes) — cada um gera
    registros independentes do mesmo arquivo baixado, sem baixar de novo. Ver `apuracao_parceiro_resumo`
    em `portal_selectors.json` pra exemplo real.

17. **Cuidado com "rollup" vs "detalhe" trazendo o MESMO valor por caminhos diferentes.** Vários
    relatórios do C6 mostram a mesma comissão/produção agregada em granularidades diferentes (por
    contrato, por Master+Produto, por Filial...). Se dois mappings usam o mesmo `metric_name`, somar no
    dashboard conta o valor em dobro/triplo. Convenção adotada: dar um `metric_name` DIFERENTE pra cada
    granularidade (ex.: `comissao_avista` no nível mais granular, `comissao_avista_por_filial` no rollup
    por filial) e documentar no `_metric_name_nota` do mapping por quê. Sempre que mapear uma tile nova,
    verifique se a soma dela bate com alguma métrica já mapeada antes de decidir o nome — se bater, é
    rollup, não dado novo (validamos isso rodando o parser contra os arquivos reais antes de gravar no
    banco, não adivinhando).

18. **`TimeoutError` esperando `get_by_role("button", name="{X} - Tile actions")`, mesmo com a tela
    carregada certinho (confirmado pelo print de falha).** O nome do botão "Tile actions" (usado no
    `tiles[].name` de `portal_selectors.json`) é o **título interno da tile no Looker**, que pode ser
    DIFERENTE do texto que aparece na barra preta visível na tela. Descoberto em 2026-09-02 (relatório
    `apuracao_parceiro_resumo`): a barra dizia "Emissão Nota Fiscal", mas o aria-label real era
    "Resumo - Valores Emissão NF". Dica prática: o nome real costuma bater com o nome do arquivo que o
    Looker sugere quando você clica "Download data" manualmente (troca `_` por espaço) — mas a forma
    confiável de confirmar é abrir o `failure_<timestamp>.html` salvo automaticamente e rodar
    `grep -o 'aria-label="[^"]*Tile actions[^"]*"'` nele; mostra o nome exato de toda tile da página.
    Corrigido assumindo que o robô SEMPRE vai bater nesse erro na primeira vez que visita um dashboard
    novo — não dá pra confiar no texto da barra preta sem confirmar contra o HTML real.

19. **`TimeoutError: Timeout ... exceeded while waiting for event "download"` numa tile que a tela mostra
    CHEIA de dados no print de falha (não "No Results") — E que já baixou certinho minutos antes no
    mesmo run.** Confirmado em teste real contra produção (2026-09-02, relatório `apuracao_parceiro_resumo`,
    tile "Resumo - Valores Emissão NF" — nome já corrigido pelo item 18, então não era mismatch de
    aria-label). Diferente do item 12 (que é a tile ainda carregando), aqui a causa é flake intermitente
    no próprio sequenciamento de clique do menu do Looker (o menu "Tile actions" às vezes não abre a
    tempo do clique seguinte "pegar"). Corrigido extraindo o download de uma tile pra um método
    `_download_tile`, decorado com o mesmo `@retry(stop=stop_after_attempt(2), wait=wait_exponential(...))`
    já usado em `_login` — e com um `page.keyboard.press("Escape")` antes de cada tentativa, pra fechar
    qualquer menu que tenha ficado aberto de um clique anterior que falhou (evita que a segunda tentativa
    clique de novo em cima de um menu já aberto e feche ele por engano). Se esse erro persistir mesmo após
    a segunda tentativa, aí sim revisitar a suspeita do item 12 (esperar um seletor de "tile carregou" por
    tile, não só a primeira).

20. **`dimension_columns` "enxuto demais" pode esconder a chave de junção que outro dado vai precisar
    depois.** Descoberto em 2026-09-03, ao planejar `base_final` (comissão de GN — ver skill
    `project-context`): tirei "Cd Contrato" de `digitacao_analitico` (relatório
    `acompanhamento_veiculos`) sem perceber que essa coluna era exatamente a chave que a planilha do
    usuário usa pra ligar cada proposta de veículo ao contrato de comissão correspondente em
    `comissao_avista`. Não era PII (só CPF/nome/telefone/placa/chassi foram excluídos de propósito, ver
    item da nota `_pii_nota`) — foi simplesmente não antecipar o uso futuro. Adicionado de volta
    (`Cd Contrato`, mais `ID Proposta`/`Cd Contrato Inter` por rastreabilidade). Lição: antes de excluir
    uma coluna não-PII de `dimension_columns` por "não parece necessária agora", verificar se ela é
    identificador/chave (contrato, proposta, loja) — essas tendem a virar join key de alguma agregação
    futura, diferente de uma coluna só descritiva.

## Fluxo de validação (sempre que mexer em seletor/fluxo novo)

Não dá pra testar a partir deste ambiente (sandbox não tem rede pros domínios do C6 — bloqueado por
política de proxy). Precisa rodar na máquina de quem tem acesso real ao portal:

```powershell
$env:HEADLESS="false"
$env:RPA_ARTIFACTS_DIR="./artifacts"
$env:RPA_BROWSER_PROFILE_DIR="./browser_profile"
python -m app.services.connectors.portal_rpa --debug
```

Com `HEADLESS=false` dá pra ver o navegador passo a passo. Em qualquer falha, o script salva
`failure_<timestamp>.png` e `.html` em `RPA_ARTIFACTS_DIR` — peça esses arquivos antes de tentar
adivinhar o que deu errado (não escreva seletor novo às cegas).

## Onde documentar o que for descoberto

Seletores e decisões vão em `backend/app/services/connectors/portal_selectors.json`, dentro de campos
`_origem`/`_atencao`/`_nota` — não só no código. Um `column_mapping`/`export_button_selector` ainda não
mapeado fica como `null`; o conector já pula esses graciosamente (loga e segue) em vez de quebrar — siga
esse padrão pra qualquer relatório novo incompleto, não trave a execução inteira por causa de uma tile
ainda não mapeada.

## Linha que não se cruza

O portal reage diferente quando percebe automação (ver item 3 acima). Isso é proteção antifraude
deliberada de uma instituição financeira. **Não tente mascarar/disfarçar a automação** (stealth plugins,
falsificar fingerprint, etc.) pra escapar dessas checagens — resolva reaproveitando sessão legítima
(perfil persistente, que é o que já fizemos), nunca simulando ser humano quando não é. Se o portal
continuar bloqueando mesmo assim, a resposta é confirmar com o C6 se a automação é permitida — não
contornar a defesa deles. Isso ainda está pendente de confirmação formal (ver skill `project-context`).
