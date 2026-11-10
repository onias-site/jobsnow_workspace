# Roteiro 13 — Quem me viu por tipo de recrutador (freelancer, mesmo domínio, outro domínio)

**Pré-requisito:** [00-preparacao-do-ambiente.md](00-preparacao-do-ambiente.md) até o item 2 (ES, APIs vis 8081 e js 8082, front 3000), `recruiterLinksSecret` na variável `application_properties`, e o roteiro 08 entendido (e-mail de currículos, **Ver currículo**, **Quem me viu**).

> **Criado em 2026-11-09**, a pedido do usuário: conferir, do ponto de vista do candidato, se a contabilidade das visualizações funciona para **freelancers**, para recrutadores **do mesmo domínio** e para recrutadores **de domínio diferente**. Só no ambiente local (e-mail mock).

## Regra que se confere

`GET /resume/{email}/viewers/{yyyyMM}` (tela **Meus dados → Quem me viu**) devolve `viewers: [{domain, views}]` do mês:

| Tipo de recrutador | Chave na grade | Como conta |
|---|---|---|
| Freelancer: e-mail num domínio do `NONPROFESSIONALDOMAINS` (gmail, hotmail, yahoo...) | `freelancer` (uma chave só para todos esses domínios) | 1 por recrutador por mês |
| Profissional, vários do mesmo domínio | o domínio (`empresa13.com.br`) | 1 por recrutador por mês: 2 recrutadores = 2 |
| Profissional de outro domínio | o domínio dele (`outra13.com.br`) | 1 por recrutador por mês |

O total ("N visualizações no mês") é a soma da grade. Rever o mesmo currículo no mesmo mês **não** conta de novo.

## Massa (`<d>` = `20261109`, senha `Roteiro@2026x`)

| Papel | E-mail |
|---|---|
| Candidato A | `cand13a.<d>@teste.com` |
| Candidato B | `cand13b.<d>@teste.com` |
| Candidato C | `cand13c.<d>@teste.com` |
| Freelancer 1 | `rec13free1.<d>@gmail.com` |
| Freelancer 2 | `rec13free2.<d>@hotmail.com` |
| Freelancer 3 | `rec13free3.<d>@yahoo.com.br` |
| Mesmo domínio 1 | `rec13a.<d>@empresa13.com.br` |
| Mesmo domínio 2 | `rec13b.<d>@empresa13.com.br` |
| Outro domínio | `rec13c.<d>@outra13.com.br` |

Cada candidato tem o seu LinkedIn (nenhum compartilhado, para não misturar com a regra do "por projeto" do roteiro 09).

## Matriz de visualizações e o esperado

| Candidato | Quem vê (em ordem; ↻ = repetição, não conta) | Esperado em Quem me viu | Total |
|---|---|---|---|
| A | free1, free2, empresa13 a, empresa13 b, outra13 c, ↻ free1, ↻ empresa13 a | `freelancer 2`, `empresa13.com.br 2`, `outra13.com.br 1` | 5 |
| B | free1, free2, free3, empresa13 a, ↻ free3 | `freelancer 3`, `empresa13.com.br 1` | 4 |
| C | free3, empresa13 a, empresa13 b, outra13 c, ↻ outra13 c, ↻ empresa13 b | `freelancer 1`, `empresa13.com.br 2`, `outra13.com.br 1` | 4 |

Os freelancers de A, B e C somam 2, 3 e 1; os do mesmo domínio, 2, 1 e 2; o de outro domínio, 1, 0 e 1.

## Automação

`automacao/13-quem-me-viu-por-tipo-de-recrutador.mjs` (rodar de dentro de `automacao`; estado em `q13-state.json`):

| Passo | Comando | Esperado |
|---|---|---|
| Q1.1 | `node 13-quem-me-viu-por-tipo-de-recrutador.mjs candidates` | 3 candidatos com sessão `ok` e save `200` |
| Q1.2 | `node 13-quem-me-viu-por-tipo-de-recrutador.mjs sessions` | 6 recrutadores `ok` |
| Q1.3 | `curl -XPOST "localhost:9200/jn_versionable,vis_resume,vis_recruiter,vis_viewed_resume/_refresh"` e, em `ccp_rest-api-tests_jobsnow`: `java @target/create-entities-args.txt ../documentation/roteiros-de-teste/automacao/SendResumesToRecruiters.java <os 6 recrutadores>` | `emailsSent: 6`; um e-mail por recrutador em `C:\logs\email\<recrutador>\` |
| Q1.4 | `node 13-quem-me-viu-por-tipo-de-recrutador.mjs links` | cada recrutador com `candidatos do roteiro A,B,C` |
| Q2 | `node 13-quem-me-viu-por-tipo-de-recrutador.mjs views` | 18 visualizações com 200 |
| Q3 | `node 13-quem-me-viu-por-tipo-de-recrutador.mjs check` | `OK` para A, B e C (sai com 0) |

> Se o `candidates` não salvar (422), ajuste o corpo do currículo pelo que a tela **Meus dados → Sobre Mim** envia (F12 → Network) e anote a diferença.
>
> **Executado em 2026-11-09:** a primeira versão do script mandava `goal: jobSearch` no `pre-registration` (422; os valores aceitos são `jobs` e `recruiting`) e guardava o `sessionToken` do `password` mesmo com `missingSaveAnswers` (201), o que levava o save do currículo a 401 `invalidSession`. Corrigido no script. O corpo do currículo foi aceito como está (200).
>
> **Q4.2 pelo Chrome:** o login de um e-mail com sessão aberta responde 409 `loginConflict`; para trocar a sessão da API (User-Agent do Node) por uma do Chrome, faça `DELETE localhost:8082/login/<e-mail>/<sessionToken>` com o User-Agent do script antes do `POST /login/<e-mail>` pelo Chrome, e guarde o token devolvido (perdê-lo exige salvar a senha de novo com o token do e-mail mock).

## Q4 — Pela tela (Chrome)

- [ ] 4.1 Pelo Chrome, abra o link (`url rec13free1.<d>@gmail.com A`) e faça o R2 do roteiro 08 (**Sim, abrir**). É uma repetição: o Quem me viu de A não muda.
- [ ] 4.2 Entre como cada candidato (helper `automacao/08-tela-curriculo-helper.js`, `switchTo`, ou sessão da API em `localhost` com o User-Agent do Chrome no `login` do `localStorage`) e abra **Meus dados → Quem me viu**, escolhendo o **mês corrente** (o campo abre no mês anterior). Esperado: o total e a grade da matriz, com a linha `freelancer` (nunca `gmail.com`, `hotmail.com` ou `yahoo.com.br`).
- [ ] 4.3 Mês anterior: "Nenhum recrutador viu o seu currículo neste mês."

## Q5 — Elasticsearch

- [ ] 5.1 `vis_viewed_resume`: 13 registros dos recrutadores do roteiro (as repetições sobrescrevem, não criam).
- [ ] 5.2 `jn_grouper` do parent `vis_resume_views_of_the_month` de cada candidato: `child` com o JSON de contadores igual ao esperado e `childCount` igual ao número de chaves (A 3, B 2, C 3).

## Limpeza (local)

Nada a apagar: o próximo reset da base local descarta tudo.
