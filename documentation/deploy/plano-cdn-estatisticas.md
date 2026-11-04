# Plano: CDN nas estatísticas das skills (`api.onias.site/statistics/skills/*`)

Escrito e aplicado em 2026-11-03, junto com a rota `/privacy-policy` da js (back-end `jobsnow-js-privacy-backend`,
invalidação no `20`). Passo 2 dispensado: o CDN guardou as respostas mesmo com o `Vary` do CORS. `localStorage` de 24
horas: aceito (primeira saída).

## Objetivo

Servir pelo Cloud CDN as três rotas públicas de estatística da vis, que são iguais para todos os usuários e só mudam
numa recarga das vagas:

| Rota | Parâmetros |
|---|---|
| `GET /statistics/skills/{yearMonth}/{seniority}/{ddd}` | path |
| `GET /statistics/skills/{seniority}/{ddd}/months?skill=...` | path + query `skill` |
| `GET /statistics/skills/telegramGroups` | nenhum |

## As rotas da tela "Grupos de vagas do telegram" (conferido em 2026-11-03)

A tela é a `SkillStatistics` do front (`presentation/pages/estatisticas/skills/SkillStatistics.tsx`), aberta pela home
já pesquisada e pela página `/estatisticas/skills`. Todas as chamadas dela que são impessoais são as três rotas acima, na
API vis (`api.onias.site`), sem sessão:

| O que a tela mostra | Chamada do front | Entra no CDN? |
|---|---|---|
| Skills do mês, da senioridade e da região (pizza e lista), botão "Todas as Vagas" | `statistics/skills/{mês}/{senioridade}/{ddd}` | Sim |
| Gráfico de linhas de uma skill, ao expandi-la | `statistics/skills/{senioridade}/{ddd}/months?skill=...` | Sim |
| Modal "Grupos pesquisados" | `statistics/skills/telegramGroups` | Sim |
| "Vagas compatíveis comigo": senioridade e DDD do currículo | `resume/{email}` (com sessão, dado pessoal) | **Não**: fica no `jobsnow-vis-backend`, sem CDN |

Depois de ler o currículo, "Vagas compatíveis comigo" faz a mesma pesquisa da primeira linha (mês anterior, senioridade e
DDD do currículo), e essa pesquisa entra no CDN como qualquer outra: a resposta não depende de quem pergunta.

Nenhuma outra rota da vis entra no plano. As demais têm `{email}` no caminho e sessão (`/resume/{email}/...`,
`/recruiter/{email}/...`), ou são `POST` (`/skills/fromText`, links do e-mail aos recrutadores). Um candidato a
avaliar depois é o autocomplete de empresas (`GET /companies/search/autocomplete/{search}`): é impessoal, mas muda a
cada carga de recrutadores e tem chaves demais (cada texto digitado) para valer o cache.

### Dois achados que mudam a validade

1. **O mês corrente ainda muda.** O front já trata disso: o mês corrente vai por `doAnAjaxRequest`, sem guardar, e só
   os meses passados vão por `doAPersistedRequest`. O CDN tem que seguir a mesma regra:
   - `{mês}` passado: `Cache-Control: public, max-age=300, s-maxage=31536000` (imutável até a próxima recarga);
   - `{mês}` corrente: `Cache-Control: public, max-age=60, s-maxage=3600` (1 hora no CDN);
   - `months?skill=...`: a resposta inclui o mês corrente, então leva a regra curta, a do mês corrente;
   - `telegramGroups`: muda só numa recarga, leva a regra longa.
   Quem decide é a vis, comparando `{mês}` com o mês corrente no fuso `America/Sao_Paulo`.
2. **O front já guarda essas respostas por 24 horas no `localStorage`** (`JnAjax.PERSISTED_REQUEST_LIFETIME`). Esse
   cache fica no navegador de cada usuário e a invalidação do CDN não o alcança. Depois de uma recarga das vagas, quem já
   abriu a tela vê os números antigos por até 24 horas, com ou sem CDN. Duas saídas, a escolher no passo 4:
   - aceitar as 24 horas (as estatísticas são mensais, o atraso de um dia pouco importa);
   - ou a vis devolver uma versão da carga (por exemplo, a data da última recarga em `telegramGroups`), e o front
     chamar `JnAjax.clearPersistedRequests()` quando a versão mudar. Isso também serve para invalidar o CDN de uma vez,
     se a versão entrar na URL.

Ganhos: a tela de estatísticas deixa de chamar a vis na maior parte das vezes, há menos partidas a frio da vis (que
escala até zero) e a resposta fica mais rápida. Custo com o tráfego atual: perto de zero.

Não é preciso trocar query parameter por path parameter: a chave do cache do Cloud CDN inclui a query string inteira por
padrão (`?skill=JAVA` e `?skill=SQL` são entradas diferentes).

## Situação de partida (conferida em 2026-11-03)

- `jobsnow-front-backend` já tem CDN (`CACHE_ALL_STATIC`), ligado pelo `09-criar-balanceador.ps1`.
- `jobsnow-vis-backend` está sem CDN e atende também rotas com sessão: **não ligar o CDN nele**.
- A resposta de produção de `/statistics/skills/telegramGroups` não tem `Cache-Control` e traz
  `Vary: Origin,Access-Control-Request-Method,Access-Control-Request-Headers` (CORS do Spring, pelo `@CrossOrigin`).
- Mapa de URLs `jobsnow-lb`: `api.onias.site` cai no path matcher `vis`, que manda tudo para `jobsnow-vis-backend`.

## Alterações no front

O CDN é transparente para o front: as URLs continuam as mesmas, em `api.onias.site`. O plano funciona sem mudar o front,
mas uma mudança pequena é recomendada para o ganho ser completo:

1. **Recomendada: não mandar os cabeçalhos de sessão nas chamadas de estatística.** Hoje o `JnAjax.doAnAjaxRequest`
   acrescenta `sessionToken` e `email` em toda requisição, inclusive nas de estatística, que são públicas. Como são
   cabeçalhos próprios numa chamada de outra origem (`onias.site` → `api.onias.site`), o navegador faz antes uma
   requisição `OPTIONS` de preflight do CORS. O Cloud CDN só guarda `GET` e `HEAD`: o preflight sempre chega à vis, e a
   partida a frio continua para o primeiro acesso de cada usuário. O navegador guarda o preflight por um tempo
   (`Access-Control-Max-Age`, 30 minutos no padrão do Spring), mas cada usuário novo paga a ida à vis.
   - Mudança: as chamadas de `statistics/skills/...` (o `doAPersistedRequest` e o `doAnAjaxRequest` do mês corrente em
     `SkillStatistics.tsx`) saem sem `sessionToken` e `email`. Sem cabeçalhos próprios, o `GET` é uma requisição simples
     do CORS, sem preflight, e o CDN atende sozinho.
   - Também deixa de passar o token da sessão por um caminho que não precisa dele.
2. **Opcional: versão da carga.** Só se for escolhida a segunda saída do item 2 de "Dois achados que mudam a validade":
   o front compara a versão devolvida pela vis com a guardada e chama `JnAjax.clearPersistedRequests()` quando mudar.

Sem o item 1, o CDN atende os `GET`, mas cada usuário novo ainda faz um `OPTIONS` à vis.

## Passo 1: cabeçalho de cache na vis

Nas três rotas acima, a resposta passa a levar um destes cabeçalhos, conforme a seção "Dois achados que mudam a
validade":

```
Cache-Control: public, max-age=300, s-maxage=31536000    (mês passado e telegramGroups)
Cache-Control: public, max-age=60, s-maxage=3600         (mês corrente e months?skill=...)
```

- `s-maxage=31536000` (1 ano, o teto do Cloud CDN): validade no CDN, renovada pela invalidação do passo 4.
- `max-age` curto: validade no navegador. O cache HTTP do navegador não pode ser invalidado, então ele fica curto. O
  `localStorage` de 24 horas do front é à parte e não muda com este cabeçalho.

Como fazer (módulo `vis_rest-api_spring_jobsnow_dependency-chooser`):

- Preferir um interceptor ou filtro do Spring registrado só para `/statistics/skills/**`, em vez de mudar o tipo de
  retorno dos métodos para `ResponseEntity` (que alteraria o contrato do `VisOpenApiSkillStatistics`).
- Só para respostas 200: um erro não pode ficar 1 ano no CDN.
- Seguir as regras do CLAUDE.md: o texto do cabeçalho em enum `CcpJsonFieldName` aninhado (LL), uma classe por arquivo
  (OTF), sem `else` (MIAEL), lambda de várias linhas vira classe (MLC).
- Teste local: `curl -s -D - -o NUL http://127.0.0.1:8081/statistics/skills/telegramGroups` mostra o `Cache-Control`;
  uma rota com sessão (por exemplo, a do currículo) continua sem ele.

## Passo 2: o `Vary` do CORS

O Cloud CDN só guarda respostas cujo `Vary` cite cabeçalhos que ele aceita (`Accept`, `Accept-Encoding`, `Origin` e
poucos outros). `Access-Control-Request-Method` e `Access-Control-Request-Headers` podem impedir o cache.

1. Depois dos passos 1 e 3, testar se o CDN guarda (passo 5). Se guardar, este passo acaba aqui.
2. Se não guardar: configurar o CORS dessas três rotas para não acrescentar esses dois cabeçalhos ao `Vary` nas respostas
   GET comuns (eles só fazem sentido na requisição `OPTIONS` de preflight). Manter `Vary: Origin`.

## Passo 3: back-end próprio com CDN e regra no mapa de URLs

Em `documentation/deploy/09-criar-balanceador.ps1` (para ficar reproduzível), acrescentar:

```powershell
# back-end das estatísticas: mesmo Cloud Run da vis, com CDN que obedece aos cabeçalhos da vis
gcloud compute backend-services create jobsnow-vis-stats-backend --global --load-balancing-scheme=EXTERNAL_MANAGED --project jobsnow-prd
gcloud compute backend-services add-backend jobsnow-vis-stats-backend --global --network-endpoint-group=jobsnow-vis-neg --network-endpoint-group-region=southamerica-east1 --project jobsnow-prd
gcloud compute backend-services update jobsnow-vis-stats-backend --global --enable-cdn --cache-mode=USE_ORIGIN_HEADERS --cache-key-include-protocol --cache-key-include-host --cache-key-include-query-string --project jobsnow-prd
```

Depois, a regra de caminho no path matcher `vis` do mapa `jobsnow-lb`:

```powershell
gcloud compute url-maps export jobsnow-lb --global --destination=jobsnow-lb.yaml --project jobsnow-prd
```

No `jobsnow-lb.yaml`, dentro de `pathMatchers` com `name: vis`, acrescentar (mantendo o `defaultService` da vis):

```yaml
  pathRules:
  - paths:
    - /statistics/skills/*
    service: https://www.googleapis.com/compute/v1/projects/jobsnow-prd/global/backendServices/jobsnow-vis-stats-backend
```

```powershell
gcloud compute url-maps import jobsnow-lb --global --source=jobsnow-lb.yaml --project jobsnow-prd
```

Opcional, contra chaves inflando o cache: na rota `months`, incluir na chave só o parâmetro `skill`
(`--cache-key-query-string-whitelist=skill`). Como o back-end é só das estatísticas e as outras duas rotas não têm query,
a lista de inclusão vale para as três sem problema.

## Passo 4: invalidar o CDN depois de cada recarga

No fim de `documentation/deploy/21-refazer-dados-das-vagas.py`, depois das contagens:

```
gcloud compute url-maps invalidate-cdn-cache jobsnow-lb --global --host api.onias.site --path "/statistics/skills/*" --async --project jobsnow-prd
```

A invalidação leva alguns minutos para chegar a todos os servidores do CDN. O cache HTTP do navegador guarda a
resposta antiga por até 5 minutos (`max-age=300`), e o `localStorage` do front por até 24 horas, salvo se for adotada a
versão da carga (seção "Dois achados que mudam a validade", item 2).

## Passo 5: ordem de execução e conferência

1. Passos 1 e 2 no código; testes locais; publicar a vis (`/ccp-deploy vis`). Se for feita a alteração recomendada do
   front (seção "Alterações no front", item 1), publicar o front também (`/ccp-deploy front`).
2. Passo 3 no balanceador.
3. Conferir, repetindo a mesma requisição duas vezes:
   ```
   curl -s -D - -o NUL "https://api.onias.site/statistics/skills/telegramGroups"
   ```
   Na segunda vez deve aparecer o cabeçalho `age:` (a cópia saiu do CDN). Repetir para uma rota de `months?skill=...`
   com duas skills diferentes e conferir que cada uma volta com os dados dela.
4. Conferir que rotas com sessão da vis (`api.onias.site/...` fora de `/statistics/skills/`) continuam sem `age:`.
5. Passo 4 no `21` e uma invalidação manual de teste.
6. Painel de monitoramento: as requisições da vis devem cair quando a tela de estatísticas for usada.

## Como desfazer

- Tirar a `pathRules` do path matcher `vis` (export, editar, import): tudo volta para `jobsnow-vis-backend`, sem CDN.
- Opcional: `gcloud compute backend-services delete jobsnow-vis-stats-backend --global --project jobsnow-prd`.
- O cabeçalho `Cache-Control` na vis pode ficar: sem CDN na frente, só o navegador o usa (5 minutos).

## Riscos

| Risco | Prevenção |
|---|---|
| Resposta de um usuário entregue a outro | CDN só no back-end das estatísticas, que são públicas e sem sessão; nunca no `jobsnow-vis-backend` |
| Estatística velha depois de uma recarga | Invalidação no fim do `21`; cache HTTP do navegador limitado a 5 minutos; `localStorage` do front de 24 horas (aceitar ou adotar a versão da carga) |
| Preflight `OPTIONS` chegando sempre à vis | Chamadas de estatística sem `sessionToken` e `email` (seção "Alterações no front", item 1) |
| Mês corrente congelado por 1 ano no CDN | Regra curta (`s-maxage=3600`) para o mês corrente e para `months?skill=...`, decidida pela vis |
| "Vagas compatíveis comigo" expondo dado pessoal | Só a pesquisa de estatística (impessoal) entra no CDN; `resume/{email}` fica no back-end sem CDN |
| Erro guardado por 1 ano | Cabeçalho só em respostas 200; o Cloud CDN guarda erros por pouco tempo (`negativeCaching`) |
| `Vary` do CORS impedindo o cache | Teste do passo 5; ajuste do passo 2 |
