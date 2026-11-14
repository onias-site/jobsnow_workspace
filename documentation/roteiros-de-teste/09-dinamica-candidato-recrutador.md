# Roteiro 09 — Dinâmica candidato/recrutador

**Pré-requisito:** [00-preparacao-do-ambiente.md](00-preparacao-do-ambiente.md) até o item 4, e o roteiro 08 entendido (e-mail de currículos, **Ver currículo**, **Quem me viu**, **Currículos visualizados**).

> **Criado e executado em 2026-11-03** (local, e-mail mock). Resultado em [resultados/2026-11-03-campanha/08-recrutador-e-quem-me-viu.md](resultados/2026-11-03-campanha/08-recrutador-e-quem-me-viu.md). A versão de produção está no [roteiro 10](10-versoes-de-producao.md).

> **Executado de novo em 2026-11-10** (local): a automação foi reescrita a partir da do roteiro 13 (contas `.20261109`: candidatos `cand09a`..`cand09f.<d>@teste.com`, F com o LinkedIn de A, B/C/D/E com `Empresa09`, `empresa 09`, `EMPRESA-09` e `pre`; recrutadores `rec09a`/`rec09b.<d>@gmail.com`, `rec091`/`rec092.<d>@empresa09.com.br`, `rec09c.<d>@consultoria09.com.br` e o logado `rec09l.<d>@teste.com`). Comandos: `candidates`, `sessions`, `recruiters` (lista para o `SendResumesToRecruiters.java`), `links` (já confere o D4), `views`, `check` (Quem me viu **e** Currículos visualizados; `check <yyyyMM>` espera vazio), `present <recrutador>`, `resave <candidato> [empresas...]`, `url`, `storage`. As sessões usam o User-Agent do Chrome 157 e valem no `localStorage` da tela. Sessões expiram em algumas horas: depois disso apague `sessions` do `dyn-state.json` e rode `sessions` de novo (cada chamada com token vencido é uma tentativa, R05-1).
>
> - O mesmo recrutador não recebe o 2º e-mail no mesmo dia (regra do "já enviado"), mas o `emailsSent` conta assim mesmo e a lista de **Currículos da semana** é regravada: confira o D4 pela API (`present`).
> - **3.4:** não passe o recrutador descadastrado ao `SendResumesToRecruiters.java`: ele grava cada argumento em `vis_recruiter`, o que o recadastra (a gêmea `vis_inactive_recruiter` perde o registro). Confira o descadastro pelo ES (`vis_recruiter` 0, `vis_inactive_recruiter` 1).
> - **4.5 pela API:** mande `notAllowedCompany: []` (como a tela). Sem o campo, o update não apaga as empresas gravadas (R09-1).

## Objetivo

Vários recrutadores de tipos diferentes recebem o e-mail de currículos e abrem alguns currículos. Depois se confere:
- o que cada recrutador vê em **Currículos visualizados**;
- o que cada candidato vê em **Quem me viu**: um por recrutador por mês, por domínio, e os gmail etc. somados sob `freelancer`.

## Massa

| Papel | Quantos | Exemplo (`<d>` = data `yyyyMMdd`) |
|---|---|---|
| Candidatos com currículo ativo, salvo nos últimos 7 dias | 6 ou mais, de tipos e pretensões diferentes; um deles com o LinkedIn de outro (C6 do roteiro 04) | `roteiro01b.<d>@teste.com`, `roteiro04a.<d>@teste.com`... |
| Recrutadores freelancers | 2 | `recrutadora.<d>@gmail.com`, `recrutadorb.<d>@gmail.com` |
| Recrutadores do mesmo domínio | 2 | `recrutador1.<d>@empresa09.com.br`, `recrutador2.<d>@empresa09.com.br` |
| Recrutador de outro domínio | 1 | `recrutador.<d>@consultoria09.com.br` |
| Recrutador logado na tela | 1 | um dos candidatos, para as telas que exigem login |

## Automação

| Arquivo | Para quê |
|---|---|
| `automacao/SendResumesToRecruiters.java` | grava os recrutadores em `vis_recruiter` (fonte "roteiro") e manda o e-mail de currículos só para eles |
| `automacao/09-dinamica-candidato-recrutador.mjs` | (reescrita em 2026-11-10, ver a nota do topo; texto antigo:) `sessions`: abre a sessão de cada recrutador (cadastro pelo token do e-mail mock); `links`: lê `GET /recruiter/{email}/resumes-of-the-week` e guarda os links assinados dos candidatos de teste; `view <recrutador> <candidato> [apelido]`: faz o que o **Sim, abrir** da tela faz; `url`: imprime o link para abrir no Chrome |

> O e-mail traz só os 30 primeiros currículos. Depois de um reset, todos os currículos contam como alterados nos últimos 7 dias, e os de teste podem ficar fora do e-mail. Por isso a automação usa a lista inteira da tela **Currículos da semana**, que é a mesma do e-mail.

## D1 — Envio

- [ ] 1.1 `curl -XPOST "localhost:9200/jn_versionable,vis_resume,vis_recruiter,vis_viewed_resume/_refresh"` e rode `SendResumesToRecruiters.java` com os 6 recrutadores. Esperado: `emailsSent: 6` e um e-mail por recrutador em `C:\logs\email\<recrutador>\`.
- [ ] 1.2 `node 09-dinamica-candidato-recrutador.mjs sessions` e depois `links`. Esperado: cada recrutador com `lista N` e `candidatos de teste 6`.

## D2 — Visualizações

- [ ] 2.1 Pelo Chrome, abra um link (`url`) de um freelancer para o candidato TI e faça o R2 do roteiro 08 (token alterado, **Não**, **Sim, abrir**, apelido).
- [ ] 2.2 Pela automação (`view`), monte uma matriz recrutador × candidato em que cada candidato tenha uma combinação diferente de domínios. Inclua uma 2ª visualização do mesmo recrutador e uma visualização do candidato que usa o LinkedIn de outro.
- [ ] 2.3 Com o recrutador logado na tela: **Currículos da semana** → **Ver currículo** de um candidato → **Sim, abrir**.

## D3 — Telas

- [ ] 3.1 **Currículos visualizados** de cada recrutador, no **mês corrente** (o campo abre no mês anterior). Esperado: um item por LinkedIn visto. Dois candidatos com o mesmo LinkedIn viram um item só.
- [ ] 3.2 **Quem me viu** de cada candidato, no mês corrente. Para entrar como cada um, abra a sessão pela API em `localhost` com o User-Agent do Chrome e ponha `{email, sessionToken}` no `login` do `localStorage` (até 2026-11-09, no `sessionStorage`; o helper `automacao/08-tela-curriculo-helper.js`, `switchTo`, já faz assim). Com sessão aberta, o `POST /login/{email}/password` com o token do primeiro cadastro desfaz o outro login. Esperado: o total e a grade por domínio da matriz do D2.2, e a 2ª visualização do mesmo recrutador não conta.
  > **Por projeto:** a visualização conta para **todos os e-mails** que usam o LinkedIn visto (`VisResumeViewsOfTheMonthCombinations`). O candidato com o LinkedIn emprestado mostra os mesmos números do dono do endereço.
- [ ] 3.3 Mês anterior: "Nenhum recrutador viu o seu currículo neste mês."
- [ ] 3.4 Descadastre um dos freelancers (R5 do roteiro 08). Rode o envio de novo num outro dia. Esperado: ele não recebe.

## D4 — Empresa indesejada

Regra (`VisBusinessSendResumesToRecruiters.isForbiddenCompany`): o currículo que cita uma empresa em **Empresas onde não quero que meu currículo seja exibido** (`notAllowedCompany`) não vai para recrutador **profissional** cujo domínio contenha o nome da empresa. O nome entra sem acento, espaço nem símbolo e precisa ser uma parte do domínio, separada por ponto ou hífen. Com 4 letras ou mais, basta estar dentro do domínio escrito sem pontos e hífens: `Itaú` barra `itau.com.br` e `itau-unibanco.com.br`. Recrutador freelancer (gmail etc.) **não** é barrado. A tela **Currículos da semana** mostra a mesma lista do e-mail, já filtrada.

- [ ] 4.1 Num dos candidatos de teste, preencha em **Meu currículo** a empresa indesejada `Empresa09` (e salve). Rode o envio (D1.1) de novo.
- [ ] 4.2 Esperado: o e-mail de `recrutador1` e o de `recrutador2` (`@empresa09.com.br`) **não** trazem esse candidato; o de `recrutador.<d>@consultoria09.com.br` e o dos freelancers trazem.
- [ ] 4.3 **Currículos da semana** (`GET /recruiter/{email}/resumes-of-the-week`) de `recrutador1`: o candidato não aparece; de um freelancer: aparece.
- [ ] 4.4 Variações: `empresa 09` com espaço e `EMPRESA-09` também barram (normalização); um nome de 3 letras que só aparece no meio do domínio não barra.
- [ ] 4.5 Tire a empresa indesejada, rode o envio de novo: o candidato volta ao e-mail de `recrutador1`.

## Limpeza (local)

Nada a apagar: o próximo reset da base local descarta tudo. As contas dos recrutadores criadas com `goal: recruiting` entram em `vis_recruiter` com a fonte `login`.
