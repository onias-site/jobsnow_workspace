# Roteiro 12 — Habilidades do meu currículo (estatísticas de skills)

**Pré-requisito:** [00-preparacao-do-ambiente.md](00-preparacao-do-ambiente.md) até o item 4 (ambiente no ar, APIs vis na 8081 e js na 8082), as vagas do Telegram carregadas no local (`executaCargaTelegram.bat`) e duas contas com senha (ver roteiro 03): uma **sem currículo** e outra com **currículo de tecnologia salvo** (ver roteiro 04).

> **Criado em 2026-11-07, ainda não executado.** Cobria o botão "Vagas compatíveis comigo" de 2026-11-01 e os selos de 2026-11-07.
>
> **Atualizado em 2026-11-07 (2):** as respostas das estatísticas passaram a ficar **um ano** no `localStorage` (antes, 24 horas); a política de privacidade continua com 24 horas. Cenário V5.
>
> **Reescrito em 2026-11-09:** o **Pesquisar** deixou de ser menu (sumiram "Todas as Vagas", "Vagas compatíveis comigo" e o modal "Escolha o DDD de preferência"); a comparação com o currículo passou para o checkbox **Ver quais dessas habilidades estão em meu currículo**, que não pesquisa. Entraram ainda: os filtros e o **Pesquisar** numa linha só, **De onde vieram essas vagas?** numa linha própria, a faixa do topo do formulário do currículo, o total acima do grid, o cargo pretendido no rótulo e no total, a validação da sessão no backend a cada clique e a pesquisa padrão ao abrir a tela. O nome do arquivo ficou o mesmo para não quebrar os links.

## Como a tela funciona (resumo)

1. **Grupos de vagas do telegram** (`/estatisticas/skills`) abre **já pesquisada** com os filtros padrão: mês anterior ao corrente, **Pleno** e **Home office** (a home, `/`, abre do mesmo jeito, mas com **Sênior**).
2. **Mês/ano**, **Senioridade**, **Região Metropolitana**, o botão **Pesquisar** e o checkbox ficam **numa linha só** (quebram apenas em tela estreita). O botão **De onde vieram essas vagas?** fica sozinho na linha de baixo e abre a lista de grupos num popover. Mudar um filtro esconde o resultado até o próximo **Pesquisar**.
3. **Pesquisar** é uma pesquisa só (a antiga "Todas as Vagas"): as skills do mês, da senioridade e da região escolhidos.
4. **Checkbox "Ver quais dessas habilidades estão em meu currículo"**: **não pesquisa**. Marcado, lê o currículo do usuário e coloca, ao lado de cada habilidade da lista, o selo verde **Você tem** ou o de contorno vermelho **Não está no seu currículo**; desmarcado, os selos somem. A lista continua a da última pesquisa, e uma pesquisa nova com o checkbox marcado já vem com selos.
   - Cada clique faz `GET localhost:8081/resume/{email}`: o backend valida a sessão, e sessão ausente, inválida ou expirada (401 `invalidSession`) abre o **modal de login**, com o checkbox desmarcado; depois de entrar, o clique continua sozinho. Até 2026-11-09 a cópia do currículo guardada no navegador bastava, sem passar pelo backend.
   - Logado e **sem currículo** (404, ou 200 sem `vis_resume` nem `vis_inactive_resume`): vai ao formulário `/meus-dados/sobre-mim`, que mostra no topo a faixa azul "Você será redirecionado à tela de estatísticas de vagas no Telegram assim que terminar o cadastro do seu currículo, que ainda não existe em nossa base de dados." Ao salvar, na mesma aba, volta a `/estatisticas/skills`, refaz a pesquisa **com os filtros de antes** (não os padrão) e marca o checkbox. Quem volta à tela de estatísticas sem salvar desiste da volta: a faixa deixa de aparecer. (sessionStorage: `compatiblePositionsWaitingForTheResume` e `compatiblePositionsFiltersOfThePendingSearch`.)
   - Currículo que não é de tecnologia: aviso "Funcionalidade disponível apenas para currículos de tecnologia (Por enquanto)", checkbox desmarcado.
   - Lido o currículo, o rótulo vira **Ver quais dessas habilidades estão em meu currículo de '&lt;cargo pretendido&gt;'** (campo `desiredJob`); antes do primeiro clique, e em currículo sem cargo, sem o trecho "de '...'".
   - Logout com o checkbox marcado: os selos e o cargo somem da tela.
5. **O que conta como "Você tem":** as habilidades da lista principal do currículo, os pais delas (gravados no currículo no dia em que foi salvo) e as implícitas. Sinônimo encontrado no texto vira o nome canônico ("Node.js" → NODE). **Pai marca, filho não:** ter NESTJS marca NODE, mas ter JAVA não marca SPRING SECURITY. As excluídas e as descartadas não contam. A comparação ignora maiúsculas, espaços das pontas e o sufixo `123` de alguns nomes.
6. **Total acima do grid:** "Total de ferramentas / habilidades / conceitos encontrados: N" (as habilidades da pesquisa). Com o checkbox marcado, acrescenta "(X (P%) estão no seu currículo de '&lt;cargo&gt;')", sobre a pesquisa inteira, com uma casa decimal e vírgula. Com texto no **Filtrar habilidades**, acrescenta "(Y com o filtro)".
7. O front guarda uma cópia reduzida do currículo em `localStorage.logins[<email>].resumeCopy[200]` (`resumeType`, `ddd`, `experienceStartYear`, `skills`), regravada a cada clique e a cada salvamento do currículo; o checkbox **não** a usa mais para decidir nada.
8. **Respostas guardadas no navegador (desde 2026-11-07, um ano):** a pesquisa (`statistics/skills/<yyyyMM>/<senioridade>/<ddd>`), o gráfico mês a mês de cada habilidade (`statistics/skills/<senioridade>/<ddd>/months?skill=...`) e os grupos do Telegram (`statistics/skills/telegramGroups`) ficam no `localStorage`, sob a chave `persistedRequest http://localhost:8081 <uri>`, com `{responseBody, expiresAt}`; `expiresAt` é o momento da gravação + 365 dias. **Desde 2026-11-10** (R12-2) a pesquisa do **mês corrente** e o gráfico mês a mês (que inclui o mês corrente) ficam só **24 horas**: o mês corrente ainda recebe vagas. Enquanto vale, a mesma pesquisa não vai ao backend; vencida, é apagada na próxima leitura e lida de novo. Mês futuro não é guardado. Pesquisa sem vagas (200 com `total: 0`) também é guardada. Se o `localStorage` enche, todas as `persistedRequest` são apagadas e a gravação é tentada de novo. **Consequência:** uma carga nova do Telegram não aparece para quem já tem a pesquisa guardada; para ver os dados novos no teste, apague as chaves (V6.5). O `GET /resume/{email}` do checkbox **nunca** é guardado.

---

## V1 — Abertura e disposição da tela

- [ ] 1.1 Abra **Grupos de vagas do telegram** (menu Estatísticas). Esperado: sem clicar em nada, "Carregando as habilidades..." e depois a pizza e o grid de **mês anterior / Pleno / Home office**; Network com `GET .../statistics/skills/<yyyyMM>/pleno/10` (ou nada, se a pesquisa já estiver guardada, V6).
- [ ] 1.2 Abra a home (`/`). Esperado: também já pesquisada, mas com **Sênior**.
- [ ] 1.3 Desktop (1360 px ou mais): Mês/ano, Senioridade, Região Metropolitana e **Pesquisar** numa linha só; o checkbox ao lado ou logo abaixo; **De onde vieram essas vagas?** sozinho na linha seguinte.
- [ ] 1.4 O botão **Pesquisar** não tem seta nem abre menu: um clique pesquisa direto.
- [ ] 1.5 **De onde vieram essas vagas?** abre a lista de grupos num popover por cima do conteúdo; clicar fora ou Esc fecha (o Esc fecha também com o foco no botão, desde 2026-11-10, R12-1).
- [ ] 1.6 Celular (390 px): os filtros quebram em várias linhas, sem rolagem horizontal da página.

## V2 — Checkbox sem login e com sessão vencida

- [ ] 2.1 Deslogado, marque o checkbox. Esperado: o modal de login abre; o checkbox continua **desmarcado**; o grid não muda.
- [ ] 2.2 Feche o modal sem entrar. Esperado: checkbox desmarcado, nenhum selo.
- [ ] 2.3 Logado, invalide a sessão sem sair do front (no DevTools, troque um caractere do `sessionToken` em `localStorage.login`) e marque o checkbox. Esperado: Network com `GET /resume/{email}` → **401**, o modal de login abre e nenhum selo aparece (até 2026-11-09 os selos apareciam pela cópia do navegador).
- [ ] 2.4 Entre pelo modal. Esperado: o clique continua sozinho, os selos aparecem e o rótulo ganha o cargo.

## V3 — Logado sem currículo: ida ao formulário e volta

- [ ] 3.1 Logado com a conta sem currículo, mude os filtros para algo diferente do padrão (por exemplo, outro mês, **Sênior** e uma região), **Pesquisar**, e marque o checkbox. Esperado: o formulário `/meus-dados/sobre-mim` com a faixa azul no topo: "Você será redirecionado à tela de estatísticas de vagas no Telegram assim que terminar o cadastro do seu currículo, que ainda não existe em nossa base de dados."
- [ ] 3.2 Preencha um currículo de tecnologia e salve. Esperado: "Currículo salvo com sucesso", volta a `/estatisticas/skills` com **os filtros da 3.1** (não os padrão), a pesquisa refeita e o checkbox **marcado**, com selos e o cargo no rótulo.
- [ ] 3.3 Recarregue a tela. Esperado: abre com a pesquisa padrão e o checkbox desmarcado (a volta é usada uma vez só).
- [ ] 3.4 Desistência: com outra conta sem currículo, repita a 3.1, mas volte ao menu **Grupos de vagas do telegram** sem salvar; depois abra **Meus dados** → currículo. Esperado: a faixa azul **não** aparece mais.

## V4 — Logado com currículo: selos, rótulo e total

- [ ] 4.1 Logado com a conta que tem currículo de tecnologia, marque o checkbox. Esperado: Network com `GET /resume/{email}` → 200 e **nenhuma** nova chamada de `statistics/skills/...` (o checkbox não pesquisa).
- [ ] 4.2 O rótulo vira **Ver quais dessas habilidades estão em meu currículo de '&lt;cargo pretendido&gt;'**, com o cargo do currículo entre aspas simples.
- [ ] 4.3 Cada linha da coluna **Habilidade** mostra **Você tem** ou **Não está no seu currículo**. Confira três **Você tem** contra a aba **Habilidades** do currículo e três **Não está no seu currículo**.
- [ ] 4.4 Implícitas e sinônimos: uma habilidade que só entrou como pai de outra (por exemplo, AGIL por SCRUM, ou POO por ANGULAR) mostra **Você tem**; uma filha de uma habilidade do currículo que não esteja nele (por exemplo, SPRING SECURITY para quem tem JAVA) mostra **Não está no seu currículo**.
- [ ] 4.5 Uma habilidade que você **excluiu** no currículo, se aparecer na lista, mostra **Não está no seu currículo**.
- [ ] 4.6 Acima do grid: "Total de ferramentas / habilidades / conceitos encontrados: N (X (P%) estão no seu currículo de '&lt;cargo&gt;')". Confira que X é o número de selos **Você tem** em todas as páginas do grid e que P = X / N × 100, com uma casa decimal e vírgula.
- [ ] 4.7 Digite parte de um nome em **Filtrar habilidades**. Esperado: N e X não mudam, aparece "(Y com o filtro)", os selos continuam nas linhas filtradas e a expansão do gráfico mês a mês funciona como antes.
- [ ] 4.8 Mude um filtro e **Pesquisar** com o checkbox marcado. Esperado: a lista nova já vem com selos e o total do currículo recalculado.
- [ ] 4.9 Desmarque o checkbox. Esperado: os selos e o trecho "(X (P%) estão no seu currículo ...)" somem; o grid e o total N continuam. O rótulo mantém o cargo.
- [ ] 4.10 Marque de novo e saia do sistema (logout no header). Esperado: o checkbox desmarca, os selos somem e o rótulo volta sem o cargo. (O logout leva à home, `/`, que abre já pesquisada com **Sênior**.)
- [ ] 4.11 No currículo, acrescente uma habilidade que estava como **Não está no seu currículo** e salve. Volte e marque o checkbox. Esperado: agora ela mostra **Você tem** (cada clique lê o currículo do backend).
  > **⚠ Atenção:** salvar um currículo que já existe é atualização, limitada a uma por dia (429).
- [ ] 4.12 Com uma conta de currículo que **não** é de tecnologia, marque o checkbox. Esperado: aviso "Funcionalidade disponível apenas para currículos de tecnologia (Por enquanto)", checkbox desmarcado.
- [ ] 4.13 Celular (390 px): o selo quebra para baixo do nome quando não cabe, e o total quebra em mais de uma linha, sem rolagem horizontal da página.

## V5 — Título da pizza

- [ ] 5.1 Em qualquer pesquisa com resultado, o accordion acima da lista diz **Ver distribuição por habilidades**. Ao abrir, a pizza e o total de vagas e de habilidades aparecem como antes.

## V6 — Estatísticas guardadas por um ano

Antes de começar, no Console da tela: `Object.keys(localStorage).filter(k => k.startsWith('persistedRequest ')).forEach(k => localStorage.removeItem(k))`. Para ver quanto falta para uma chave vencer, em dias: `(JSON.parse(localStorage.getItem('<chave>')).expiresAt - Date.now()) / 86400000`.

- [ ] 6.1 Recarregue a tela (a pesquisa padrão roda sozinha) e depois **Pesquisar** com um mês passado, uma senioridade e uma região. Esperado: Network com `GET .../statistics/skills/<yyyyMM>/<senioridade>/<ddd>` para cada uma; no `localStorage`, a chave `persistedRequest http://localhost:8081 statistics/skills/<yyyyMM>/<senioridade>/<ddd>`, vencendo em **cerca de 365 dias**.
- [ ] 6.2 Repita a mesma pesquisa (e recarregue a página e repita de novo). Esperado: a lista aparece igual e **nada** no Network, nem a pesquisa padrão da abertura.
- [ ] 6.3 Expanda uma habilidade da lista (gráfico mês a mês). Esperado: `GET .../months?skill=...` na primeira vez, chave `persistedRequest ... months?skill=...` com cerca de **24 horas** (365 dias até 2026-11-10, R12-2); recolher e expandir de novo não vai ao backend.
- [ ] 6.3b **Pesquisar** com o **mês corrente**. Esperado: a chave `persistedRequest ... statistics/skills/<yyyyMM do mês corrente>/...` vence em cerca de **24 horas** (desde 2026-11-10, R12-2), e não em 365 dias como a dos meses passados.
- [ ] 6.4 Abra **De onde vieram essas vagas?**. Esperado: chave `persistedRequest ... statistics/skills/telegramGroups` com cerca de 365 dias; reabrir não vai ao backend.
- [ ] 6.5 Apague só a chave da 6.1 e pesquise de novo. Esperado: o `GET` volta ao Network e a chave é regravada com um ano.
- [ ] 6.6 Pesquisa de um **mês futuro**. Esperado: vai ao backend toda vez e não grava chave.
  > **Executado em 2026-11-10:** o seletor de mês/ano não oferece mês futuro (vai até o mês corrente, `MonthPicker.tsx`/`months.ts`), então este passo não se faz pela tela; a regra (`SkillStatistics.tsx:529-532`) só vale para quem chama a URL. O **mês corrente** não conta como futuro; até 2026-11-10 era guardado por um ano, como os passados (R12-2), e agora é guardado por 24 horas.
- [ ] 6.7 Marque e desmarque o checkbox algumas vezes (logado, com currículo). Esperado: `GET /resume/{email}` a cada marcação e nenhuma chave `persistedRequest` dele.
- [ ] 6.8 Abra `/privacidade`. Esperado: a chave `persistedRequest http://localhost:8082 privacy-policy?language=...` vence em **cerca de 1 dia** (a política continua com 24 horas).
- [ ] 6.9 Vencimento: troque o `expiresAt` da chave da 6.1 por um valor no passado (`const k = '<chave>'; const v = JSON.parse(localStorage.getItem(k)); v.expiresAt = Date.now() - 1; localStorage.setItem(k, JSON.stringify(v))`) e pesquise de novo. Esperado: o `GET` volta ao Network e a chave é regravada com um ano.
