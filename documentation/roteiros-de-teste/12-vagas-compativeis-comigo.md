# Roteiro 12 — Vagas compatíveis comigo (estatísticas de skills)

**Pré-requisito:** [00-preparacao-do-ambiente.md](00-preparacao-do-ambiente.md) até o item 4 (ambiente no ar, APIs vis na 8081 e js na 8082), as vagas do Telegram carregadas no local (`executaCargaTelegram.bat`) e duas contas com senha (ver roteiro 03): uma **sem currículo** e outra com **currículo de tecnologia salvo** (ver roteiro 04).

> **Criado em 2026-11-07, ainda não executado.** Cobre o botão de 2026-11-01 e, de 2026-11-07, o selo de cada habilidade ("Você tem" / "Não está no seu currículo") e o novo título da pizza ("Ver distribuição por habilidades").
>
> **Atualizado em 2026-11-07 (2):** as respostas das estatísticas passaram a ficar **um ano** no `localStorage` (antes, 24 horas); a política de privacidade continua com 24 horas. Cenário V5.

## Como a tela funciona (resumo)

1. **Grupos de vagas do telegram** (`/estatisticas/skills`): o botão **Pesquisar** abre **Todas as Vagas** (mês, senioridade e região escolhidos nos filtros) e **Vagas compatíveis comigo**.
2. **Vagas compatíveis comigo** pesquisa o mês anterior ao corrente, com a senioridade calculada pelo ano de início da experiência do currículo e o DDD do currículo. Com mais de um DDD, um modal pede para escolher um. Os filtros passam a mostrar o que foi pesquisado. Currículo que não é de tecnologia: aviso "Funcionalidade disponível apenas para currículos de tecnologia (Por enquanto)", sem pesquisa.
3. O front guarda uma cópia reduzida do currículo em `localStorage.logins[<email>].resumeCopy[200]`: `resumeType`, `ddd`, `experienceStartYear` e (desde 2026-11-07) `skills`, os nomes das habilidades do currículo em minúsculas. Contam as da lista principal e as implícitas; as excluídas e as descartadas não. Uma cópia sem `skills` (gravada antes de 2026-11-07) é ignorada, e o currículo é lido de novo com `GET localhost:8081/resume/{email}`.
4. Sem currículo salvo (404, ou 200 sem `vis_resume` nem `vis_inactive_resume`), a tela avisa "Preencha o seu currículo — Ao salvar, voltamos para a pesquisa de vagas compatíveis com você." e leva ao formulário. Depois de salvar, na mesma aba, ela volta à pesquisa e a refaz sozinha (marca `compatiblePositionsWaitingForTheResume` no sessionStorage).
5. Na pesquisa compatível, cada linha da lista de habilidades mostra, ao lado do nome: selo verde **Você tem** (ícone de check) quando o currículo tem a habilidade, selo de contorno vermelho **Não está no seu currículo** (ícone de ×) quando não tem. A comparação ignora maiúsculas e o sufixo `123` de alguns nomes. **Todas as Vagas** não mostra selos.
6. **Respostas guardadas no navegador (desde 2026-11-07, um ano):** a pizza de cada pesquisa (`statistics/skills/<yyyyMM>/<senioridade>/<ddd>`), o gráfico mês a mês de cada habilidade (`statistics/skills/<senioridade>/<ddd>/months?skill=...`) e os grupos do Telegram (`statistics/skills/telegramGroups`) ficam no `localStorage`, sob a chave `persistedRequest http://localhost:8081 <uri>`, com `{responseBody, expiresAt}`; `expiresAt` é o momento da gravação + 365 dias (era + 24 horas). Enquanto vale, a mesma pesquisa não vai ao backend; vencida, é apagada na próxima leitura e lida de novo. Mês futuro não é guardado. Pesquisa sem vagas (200 com `total: 0`) também é guardada. Se o `localStorage` enche, todas as `persistedRequest` são apagadas e a gravação é tentada de novo. **Consequência:** uma carga nova do Telegram não aparece para quem já tem a pesquisa guardada; para ver os dados novos no teste, apague as chaves (V5.5).

---

## V1 — Logado sem currículo

- [ ] 1.1 Logado com a conta sem currículo, abra **Grupos de vagas do telegram** → **Pesquisar** → **Vagas compatíveis comigo**. Esperado: aviso "Preencha o seu currículo" e o formulário do currículo (`/meus-dados/sobre-mim`).
- [ ] 1.2 Preencha um currículo de tecnologia, com um DDD só, e salve. Esperado: "Currículo salvo com sucesso", volta a `/estatisticas/skills` e a pesquisa compatível roda sozinha, com os filtros no mês anterior, na senioridade da experiência e no DDD do currículo.
- [ ] 1.3 Esperado: cada habilidade da lista tem um selo; as que você pôs no currículo (e as implícitas delas) mostram **Você tem**.
- [ ] 1.4 Recarregue a tela. Esperado: não refaz a pesquisa sozinha (a marca do sessionStorage é usada uma vez só).

## V2 — Logado com currículo: selos

- [ ] 2.1 Logado com a conta que tem currículo de tecnologia, **Pesquisar** → **Vagas compatíveis comigo**. Esperado: a lista sem passar pelo formulário (com mais de um DDD, primeiro o modal "Escolha o DDD de preferência").
- [ ] 2.2 Esperado: cada linha da coluna **Habilidade** mostra **Você tem** ou **Não está no seu currículo**. Confira três habilidades com selo **Você tem** contra a aba **Habilidades** do currículo, e três com **Não está no seu currículo**.
- [ ] 2.3 Uma habilidade que você **excluiu** no currículo, se aparecer na lista, mostra **Não está no seu currículo**.
- [ ] 2.4 Filtre a lista pelo nome de uma habilidade e expanda a linha (gráfico mês a mês). Esperado: o selo continua na linha filtrada, e a expansão funciona como antes.
- [ ] 2.5 **Pesquisar** → **Todas as Vagas**. Esperado: a lista volta sem nenhum selo.
- [ ] 2.6 Celular (largura de 390 px): o selo quebra para baixo do nome quando não cabe, sem rolagem horizontal da página.

## V3 — Cópia antiga e atualização do currículo

- [ ] 3.1 No DevTools, apague o campo `skills` de `localStorage.logins[<email>].resumeCopy[200]` e pesquise **Vagas compatíveis comigo**. Esperado: a aba Rede mostra `GET /resume/{email}`, os selos aparecem certos e a cópia volta a ter `skills`.
- [ ] 3.2 No currículo, acrescente uma habilidade que estava como **Não está no seu currículo** e salve. Volte e pesquise de novo. Esperado: agora ela mostra **Você tem**.
  > **⚠ Atenção:** salvar um currículo que já existe é atualização, limitada a uma por dia (429).

## V4 — Título da pizza

- [ ] 4.1 Em qualquer pesquisa com resultado, o accordion acima da lista diz **Ver distribuição por habilidades** (até 2026-11-07 dizia "Ver distribuição por vagas"). Ao abrir, a pizza e o total de vagas e de habilidades aparecem como antes.

## V5 — Estatísticas guardadas por um ano

Antes de começar, no Console da tela: `Object.keys(localStorage).filter(k => k.startsWith('persistedRequest ')).forEach(k => localStorage.removeItem(k))`. Para ver quanto falta para uma chave vencer, em dias: `(JSON.parse(localStorage.getItem('<chave>')).expiresAt - Date.now()) / 86400000`.

- [ ] 5.1 **Todas as Vagas** com um mês passado, uma senioridade e uma região. Esperado: Network com `GET .../statistics/skills/<yyyyMM>/<senioridade>/<ddd>`; no `localStorage`, a chave `persistedRequest http://localhost:8081 statistics/skills/<yyyyMM>/<senioridade>/<ddd>`, vencendo em **cerca de 365 dias** (não 1).
- [ ] 5.2 Repita a mesma pesquisa (e recarregue a página e repita de novo). Esperado: a lista aparece igual e **nada** no Network.
- [ ] 5.3 Expanda uma habilidade da lista (gráfico mês a mês). Esperado: `GET .../months?skill=...` na primeira vez, chave `persistedRequest ... months?skill=...` com cerca de 365 dias; recolher e expandir de novo não vai ao backend.
- [ ] 5.4 Abra o accordion **De onde vieram essas vagas?**. Esperado: chave `persistedRequest ... statistics/skills/telegramGroups` com cerca de 365 dias; reabrir não vai ao backend.
- [ ] 5.5 Apague só a chave da 5.1 e pesquise de novo. Esperado: o `GET` volta ao Network e a chave é regravada com um ano.
- [ ] 5.6 Pesquisa de um **mês futuro**. Esperado: vai ao backend toda vez e não grava chave.
- [ ] 5.7 Abra `/privacidade`. Esperado: a chave `persistedRequest http://localhost:8082 privacy-policy?language=...` vence em **cerca de 1 dia** (a política continua com 24 horas).
- [ ] 5.8 Vencimento: troque o `expiresAt` da chave da 5.1 por um valor no passado (`const k = '<chave>'; const v = JSON.parse(localStorage.getItem(k)); v.expiresAt = Date.now() - 1; localStorage.setItem(k, JSON.stringify(v))`) e pesquise de novo. Esperado: o `GET` volta ao Network e a chave é regravada com um ano.
