# Roteiro 05 — Endpoints do currículo pela tela (`VisRestApiResume`)

**Pré-requisito:** [00-preparacao-do-ambiente.md](00-preparacao-do-ambiente.md) até o item 4 (Elasticsearch, APIs js 8082 e vis 8081, front 3000 e login).

> **Criado e executado em 2026-10-15**, no Chrome, com 10 candidatos novos (`roteiro05.*.593167@teste.com`) e o helper `automacao/08-tela-curriculo-helper.js`, que preenche as abas e clica nos botões de verdade. Resultado na seção [Execução de 2026-10-15](#execução-de-2026-10-15), no fim. Cobre só os quatro endpoints do controller `VisRestApiResume`, sempre a partir de uma ação do candidato na tela "Sobre mim" (`http://localhost:3000/meus-dados/sobre-mim`; até 2026-10-17, "Ver meu currículo" em `/portuguese-version/como-estou-indo/ver-meu-curriculo`).

> **Executado de novo em 2026-10-26** no Chrome, junto com o roteiro 04, com `roteiro03.20261026@teste.com` (duas abas) e, para o tipo 4 e o LinkedIn emprestado, `roteiro01b.20261026@teste.com` pela API. Todos os passos conferiram, inclusive as correções R05-1 (aviso e formulário limpo depois do 404) e R05-2 (sem `hash` no `GET`). Para provocar o 401 com o currículo na tela (2.6, 3.5, 4.5), a sessão foi encerrada no servidor (`DELETE /login/{email}/{sessionToken}` na 8082) deixando a da aba como estava: trocar o `sessionToken` por um inventado faz o login seguinte cair em "Desbloqueie seu login" (409), porque a sessão verdadeira continua sendo a corrente. Resultado na seção [Execução de 2026-10-26](#execução-de-2026-10-26). A sugestão de habilidade e a sugestão de ajuste de hierarquia (outros controllers) ficam fora: estão nos roteiros 01 e 02. As chamadas de apoio da tela (`skills/fromText`, `companies/search/autocomplete`) aparecem só porque a tela precisa delas para montar o currículo.

> **Executado de novo em 2026-11-03** com `roteiro01b` e `roteiro05a.20261103@teste.com` (sessão aberta pela API js com o User-Agent do Chrome, em `localhost`, porque a sessão vale para o IP e o User-Agent de quem a abriu). Sem defeitos. Resultado em [resultados/2026-11-03-campanha/05-endpoints-do-curriculo-pela-tela.md](resultados/2026-11-03-campanha/05-endpoints-do-curriculo-pela-tela.md).

> **Executado de novo em 2026-11-09/10** (Chrome, `roteiro05a`..`05g.20261109@teste.com`; tipos 3 e 4 e o LinkedIn emprestado pela API). Textos dos passos 1.4, 2.1, 2.7, 2.8 e 2.11 atualizados para o front de 2026-11-08 (prévia ao salvar, botão Ver prévia, pendências ao avançar, home office como checkbox, marca Onias.Site). **Atenção ao 1.2/1.2b:** o token inventado conta uma tentativa de sessão, e logo depois do login a tela dispara dois `GET /resume` que dão 401 enquanto a sessão ainda é gravada (escrita assíncrona); as três juntas bloqueiam a senha e o login seguinte do mesmo candidato (2.6, 3.5, 4.5) cai em "Desbloqueie a sua senha" (423). Até a correção do defeito, faça o 1.2 com um candidato que não será usado depois.

## Os quatro endpoints

| # | Endpoint | Serviço | O que a tela faz para chamá-lo | Respostas esperadas |
|---|---|---|---|---|
| 1 | `GET /resume/{email}` | `VisServiceResume.GetData` | abrir ou recarregar a tela | 200 com o registro debaixo de `vis_resume` (ativo) ou `vis_inactive_resume` (inativo), ou sem nenhum dos dois (sem currículo); 401 sem sessão, sem modal: a faixa azul "Você não está logado! ... faça login ..." (desde 2026-11-07) |
| 2 | `POST /resume/{email}/language/portuguese` | `VisServiceResume.Save` | **Salvar dados**, na última aba ou, na edição, o verde das outras abas (desde 2026-11-07); na edição, depois da confirmação "Atualizar currículo" | 200 com só os campos do currículo; 422 se o corpo violar a regra de algum campo; 429 na segunda **atualização** do dia (cadastrar não tem limite); 401 sem sessão (abre o modal de login e salva depois dele) |
| 3 | `DELETE /resume/{email}/language/portuguese/status` | `VisServiceResume.ChangeStatus` | **Inativar** ou **Reativar**, na faixa de situação | 200; 404 quando o currículo não existe mais (a tela relê a situação); 429 na segunda inativação (ou reativação) do dia; 401 sem sessão (modal de login e refaz) |
| 4 | `DELETE /resume/{email}/language/portuguese` | `VisServiceResume.Delete` | **Excluir**, na faixa de situação | 200; 429 na segunda exclusão do dia, mesmo depois de cadastrar de novo; 401 sem sessão (modal de login e refaz) |

> **Uma ação de cada tipo por dia** (desde 2026-11-07, item 5B do roteiro 00): atualizar, inativar, reativar e excluir valem uma vez a cada 24 horas por candidato, gravadas em `vis_resume_daily_action`; a tela guarda a mesma marca no `localStorage` (`resumeDailyActions`) e, com ela, avisa sem chamar o backend. Vários cenários abaixo repetem uma ação com o mesmo candidato (2.3 e 2.5 são duas atualizações; 3.1, 3.4 e 3.5 são inativações): **antes de cada um, use um candidato novo ou libere o dia** (`automacao/libera-cota.ps1 -Indices vis_resume_daily_action` e, no Console, `localStorage.removeItem('resumeDailyActions')`).

## O que conferir fora da tela

| O que | Onde |
|---|---|
| Requisição e resposta | F12 → **Network**, filtro `resume` |
| Currículo ativo | `http://localhost:9200/vis_resume/_search?pretty` |
| Currículo inativo | `http://localhost:9200/vis_inactive_resume/_search?pretty` |
| E-mails do LinkedIn | `http://localhost:9200/vis_resume_linkedin/_search?pretty` (campo `emails`, com os hashes) |
| Agrupadores | `jn_grouper` (ativos) e `jn_inactive_grouper` (inativos), filtrando por `child` |
| Ações do dia (desde 2026-11-07) | `http://localhost:9200/vis_resume_daily_action/_search?pretty` (campo `action`: `update`, `inactivation`, `reactivation`, `exclusion`; o e-mail é hash) e, no navegador, `localStorage.getItem('resumeDailyActions')` |
| E-mail ao candidato | `C:\logs\email\<e-mail>\com.vis.messages.VisMessages$VisNotifyUserAbout<Ação>Resume.html`, com `<Ação>` = `Saved`, `Deactivated`, `Reactivated` ou `Deleted` |

> O Elasticsearch mostra uma escrita só depois do refresh (cerca de 1 s): espere um instante antes de conferir.

## Massa

Use candidatos novos, um por cenário, para que um cenário não dependa do anterior: `roteiro05.<cenário>.<hora>@teste.com`. Abra a sessão de cada um pelo modal de login (roteiro 03) ou pela API js com o User-Agent do navegador, como faz `automacao/07-amostra-para-tela.mjs`, e ponha no `localStorage` (`login` = `{email, sessionToken}`; até 2026-11-09, no `sessionStorage`). A sessão vale para todas as abas do navegador: dois candidatos ao mesmo tempo pedem uma janela anônima ou outro navegador.

---

## E1 — Ler o currículo ao abrir a tela (`GET /resume/{email}`)

- [ ] 1.1 **Sem login**: no Console, `localStorage.removeItem('login'); localStorage.removeItem('logins')` e recarregue. Esperado: faixa azul "Você não está logado! Caso tenha cadastrado currículo conosco, faça login que seus dados aparecerão aqui." (desde 2026-11-07; antes, nenhuma faixa), formulário vazio, **nenhum modal de login** aberto sozinho; no Network, nenhum `GET /resume` sai (o front barra antes de enviar, sem sessão).
- [ ] 1.2 **Sessão inválida**: ponha no `localStorage` um `login` com `sessionToken` inventado e recarregue. Esperado: `GET /resume` → 401; a faixa azul do 1.1, **nenhum modal**.
- [ ] 1.2b **Login pela faixa** (desde 2026-11-07): clique em **faça login**. Esperado: o modal de login abre; depois de autenticar, sai um novo `GET /resume` → 200 e a faixa e as abas mostram o currículo gravado (ou "Você ainda não tem currículo salvo").
- [ ] 1.3 **Candidato sem currículo**: logado, recarregue. Esperado: `GET /resume` → 200 sem `vis_resume` nem `vis_inactive_resume`; faixa cinza "Você ainda não tem currículo salvo", **sem botões**; formulário vazio.
- [ ] 1.4 **Currículo ativo**: recarregue depois do E2. Esperado: 200 com `vis_resume`; faixa verde "Currículo ativo: visível para os recrutadores" com **Ver prévia**, **Inativar** e **Excluir** (desde 2026-11-08); as abas voltam preenchidas com o que foi salvo (no TI, a aba **N Habilidades** com as habilidades gravadas, sem precisar colar o texto).
- [ ] 1.5 **Currículo inativo**: recarregue depois do 3.1. Esperado: 200 com `vis_inactive_resume`; faixa laranja "Currículo inativo: oculto dos recrutadores" com **Reativar** e **Excluir**; abas preenchidas.
- [ ] 1.6 **A resposta não expõe a sessão**: no Network, a resposta do 1.4 não tem `sessionToken`, `ip` nem `userAgent`.

## E2 — Salvar (`POST /resume/{email}/language/portuguese`)

- [ ] 2.1 **Inclusão, tipo 1 (TI)**: aba Currículo: função buscada, última função, LinkedIn `https://www.linkedin.com/in/roteiro05-<hora>`, uma empresa pelo autocomplete e outra digitada + Enter, tipo "Tecnologia da Informação" e o texto do currículo (com JAVA e SPRING BOOT). Avance por Idiomas, Habilidades, Opções (uma região, experiência, disponibilidade, temporário) e Salários (CLT). **Salvar dados**. Esperado: `POST` → 200; toast "Currículo salvo com sucesso" com o detalhe "Seu currículo está ativo e visível para os recrutadores."; a tela vai para a **Prévia do currículo** (`/meus-dados/sobre-mim/previa`, desde 2026-11-08; o mesmo depois de cada salvar com 200, inclusive 2.3, 2.3b, 2.5 e 2.6); de volta a "Sobre mim", faixa verde com **Ver prévia**, **Inativar** e **Excluir**; `vis_resume` com os campos; `vis_resume_linkedin` com o endereço e um hash em `emails`; e-mail `...SavedResume.html`.
- [ ] 2.2 **A resposta não expõe a sessão**: a resposta do 2.1 traz só campos do currículo (sem `sessionToken`, `ip`, `userAgent`).
- [ ] 2.3 **Atualização**: troque a função buscada, avance até Salários e salve. Esperado (desde 2026-11-07): antes do `POST`, a confirmação "Atualizar currículo — Os dados do seu currículo serão substituídos pelos desta tela. Tem certeza de que deseja atualizar o currículo? Atenção: só é possível atualizar o currículo uma única vez ao dia." → **Sim, atualizar**; 200; `vis_resume` com a função nova; continua um só registro; registro `update` em `vis_resume_daily_action`. Com **Não**, nenhuma requisição.
- [ ] 2.3b **Salvar pelo botão verde** (desde 2026-11-07): com o dia liberado, na aba **Idiomas** troque um nível e clique no **Salvar dados** verde. Esperado: a mesma confirmação do 2.3 e o mesmo `POST` → 200.
- [ ] 2.3c **Segunda atualização do dia**: depois do 2.3, salve de novo. Esperado: aviso vermelho "Só é possível atualizar o currículo uma única vez ao dia, e você já fez isso. Poderá fazer de novo a partir de ..."; sem confirmação, **nenhum** `POST`. Apague só a marca do navegador (`localStorage.removeItem('resumeDailyActions')`) e salve → confirme: `POST` → 429, aviso "Limite diário atingido — ... nas últimas 24 horas. Tente de novo amanhã."; `vis_resume` sem a mudança.
- [ ] 2.4 **Tipos 2, 3 e 4**: com outro candidato para cada tipo, preencha e salve. Esperado: sem a aba Habilidades; nenhum `POST skills/fromText`; 200 e o registro com `skill` vazio.
- [ ] 2.5 **Salvar um currículo inativo reativa**: com o currículo inativo (3.1), mude um campo e salve (é uma **atualização**: confirmação do 2.3 e, se o 2.3 foi feito com o mesmo candidato, libere o dia antes). Esperado: 200; faixa verde; o registro sai de `vis_inactive_resume` e volta a `vis_resume`.
- [ ] 2.6 **Sessão expirada no salvar**: com a tela preenchida, encerre a sessão no servidor (Console: `fetch('http://localhost:8082/login/<email>/<sessionToken>', {method:'DELETE', headers:{'Content-Type':'application/json', sessionToken:'<sessionToken>', email:'<email>'}, body:'{}'})`, com os valores de `localStorage.getItem('login')`) e clique **Salvar dados**. Esperado: `POST` → 401 e o modal de login abre; depois de logar, o salvar é refeito sozinho e responde 200.
- [ ] 2.7 **Validações da tela barram o salvar** (nada sai para o `POST`): LinkedIn terminado em hífen; empresa com mais de 50 caracteres; experiência 71; temporário 13; sem CLT nem PJ. Esperado (desde 2026-11-08): o botão **não** fica desabilitado; ao clicar **Avançar**/**Salvar dados** a aba não muda, nada sai para a rede e aparecem a mensagem da regra no campo, a caixa "Para continuar, resolva:" e o toast "Falha!!!". Exceções: a empresa é cortada no 50º caractere ao digitar (`maxLength`, achado R04-3) e a experiência 71 vira 70 (máximo) ao sair do campo.
- [ ] 2.8 **Home office e regiões** (desde 2026-11-08 o home office é o checkbox "Aceito somente vagas home office", marcado no currículo novo, e a lista de regiões só aparece com ele desmarcado; os avisos "Regiões desmarcadas" e "Home office desmarcado" saíram, `TabFilter/RegioesComponent.tsx:65-67`): desmarque o home office, escolha três regiões e marque o home office de novo. Esperado: a lista some e as regiões são descartadas sem aviso (ao desmarcar, a lista volta vazia); salvar com home office sozinho → 200 com `ddd: [10]`.
- [ ] 2.9 **LinkedIn de outro e-mail**: com um segundo candidato, salve com o LinkedIn do 2.1. Esperado: 200; `vis_resume_linkedin` com os dois hashes em `emails`; o operador recebe no Telegram (real) o aviso de LinkedIn compartilhado.
- [ ] 2.10 **Devolver o LinkedIn emprestado**: o segundo candidato troca para um LinkedIn próprio e salva. Esperado: 200; o endereço do 2.1 fica só com o hash do primeiro candidato.
- [ ] 2.11 **E-mail do currículo salvo** (desde 2026-11-07), aberto no navegador a partir de `C:\logs\email\<e-mail>\com.vis.messages.VisMessages$VisNotifyUserAboutSavedResume.html`, depois do 2.1 e de novo depois do 2.3. Esperado, igual na inclusão e na atualização:
  - assunto "O seu currículo foi salvo" (o arquivo guarda só o corpo: confira o assunto no registro do envio, `jn_email_message_sent`);
  - "Olá, aqui é o Onias, do Onias.Site. Os dados do seu currículo foram salvos." (até a marca Onias.Site, "do JobsNow"), com o nome ligado ao LinkedIn do Onias;
  - o parágrafo "A partir de agora, o seu currículo entra no e-mail que os recrutadores recebem com os currículos inseridos ou alterados nos últimos 7 dias. Cada vez que você atualizar os seus dados, ele volta a aparecer nesse e-mail por mais 7 dias.";
  - o título "Como o recrutador verá o seu currículo" e "Confira abaixo, com os dados que você acabou de salvar...", com o link **corrija no formulário** para `http://localhost:3000/meus-dados/sobre-mim` e a lembrança das empresas indesejadas;
  - a tabela dos recrutadores com **uma linha**, a do currículo com o que foi salvo **agora** (no 2.3, a função nova): as 5 colunas; em "Datas e visualização" só "Você nunca visualizou este currículo" e **Ver currículo** como texto, **sem** linhas de data (o histórico só sai por consulta, que a gravação não faz);
  - **nenhuma** frase do convite aos candidatos legados ("há algum tempo", "cadastro antigo", "Este convite é único");
  - no fim, o rodapé com **Política de privacidade**.
- [ ] 2.12 **Mais de 15 habilidades e mais de 3 regiões no e-mail**: salve um TI cujo texto renda mais de 15 habilidades, com 5 regiões. Esperado no e-mail do 2.11: as 15 primeiras linhas de "Idiomas e habilidades" (inglês e espanhol fluentes, as habilidades pela posição no ranking de `vis_skill`, os outros idiomas) e o link **ver as outras N habilidades**; as 3 primeiras regiões e o link **+2 regiões**. Os dois links levam ao formulário, e o `title` de cada um lista o que ficou de fora, separado por vírgula (passe o mouse: a dica aparece). No código-fonte, **nenhum** `<details>`, e as habilidades e regiões de fora **não** aparecem como linhas.

## E3 — Inativar e reativar (`DELETE /resume/{email}/language/portuguese/status`)

- [ ] 3.1 **Inativar, sem sair da primeira aba**: **Inativar** na faixa → confirmação "Seu currículo deixará de aparecer para os recrutadores até que você o reative. Tem certeza de que deseja inativar o currículo? Atenção: só é possível inativar o currículo uma única vez ao dia." → **Sim, inativar**. Esperado: `DELETE .../status` → 200; toast "Currículo inativado" com o detalhe "Seu currículo não aparece mais para os recrutadores até que você o reative."; faixa laranja com **Reativar** e **Excluir**; registro em `vis_inactive_resume` e grupos em `jn_inactive_grouper`; registro `inactivation` em `vis_resume_daily_action`; e-mail `...DeactivatedResume.html` (conteúdo no 3.1b).
- [ ] 3.1b **E-mail do currículo inativado** (desde 2026-11-09; antes era uma frase só, sem tabela), aberto no navegador a partir de `C:\logs\email\<e-mail>\com.vis.messages.VisMessages$VisNotifyUserAboutDeactivatedResume.html`, depois do 3.1. Esperado, no mesmo formato do e-mail do currículo salvo (2.11):
  - assunto "O seu currículo foi inativado" (confira no registro do envio, `jn_email_message_sent`);
  - "Olá, aqui é o Onias, do Onias.Site. Você inativou seus dados.", com o nome ligado ao LinkedIn do Onias;
  - o aviso "O seu currículo deixou de ser visto pelos recrutadores. A partir de agora, ele não entra mais no e-mail que os recrutadores recebem com os currículos inseridos ou alterados nos últimos 7 dias.";
  - "Os seus dados continuam guardados. Quando quiser voltar a ser visto, **reative o seu currículo**: ele volta a aparecer para os recrutadores com os mesmos dados.", com o link para `http://localhost:3000/meus-dados/sobre-mim` (lá está o **Reativar** da faixa);
  - o título "Como os recrutadores viam o seu currículo" e "Confira abaixo, com os dados guardados do seu currículo.";
  - a tabela dos recrutadores com **uma linha**, a do currículo inativado (lido de `vis_inactive_resume`), com as 5 colunas, como no 2.11; **nenhum** `{resumesTable}` cru;
  - **nenhuma** frase de salvar ou reativar ("foram salvos", "reativou", "corrija no formulário");
  - no fim, o rodapé com **Política de privacidade**.
- [ ] 3.2 **Reativar**: **Reativar** → confirmação com "... só é possível reativar o currículo uma única vez ao dia." → **Sim, reativar**. Esperado: 200; toast "Currículo reativado" com "Seu currículo voltou a aparecer para os recrutadores."; faixa verde; de volta a `vis_resume` e `jn_grouper`; registro `reactivation`; e-mail `...ReactivatedResume.html`.
- [ ] 3.2b **Segunda inativação do dia** (desde 2026-11-07): depois do 3.2, **Inativar**. Esperado: aviso "Limite diário atingido — Só é possível inativar o currículo uma única vez ao dia, e você já fez isso. Poderá fazer de novo a partir de ..."; sem confirmação, **nenhum** `DELETE .../status`. Apague só a marca do navegador e repita: `DELETE .../status` → 429, aviso "... nas últimas 24 horas. Tente de novo amanhã.", faixa verde mantida; a resposta do 429 traz só `message` e `status`.
- [ ] 3.3 **Desistir na confirmação**: **Inativar** → **Não**. Esperado: nenhuma requisição; nada muda.
- [ ] 3.4 **Currículo excluído em outra aba**: abra a tela em duas abas com o mesmo candidato (desde 2026-11-09 a segunda aba já entra logada, sem modal); exclua na primeira; na segunda, **Inativar** → **Sim**. Esperado: `DELETE .../status` → 404; a segunda aba relê a situação e mostra "Você ainda não tem currículo salvo", sem botões.
- [ ] 3.5 **Sessão expirada**: encerre a sessão no servidor como no 2.6 e clique **Inativar** → **Sim**. Esperado: 401, modal de login; depois de logar, a inativação é refeita (200).
- [ ] 3.6 **Resposta sem dados da sessão**: a resposta do 3.1 não traz `sessionToken`, `ip` nem `userAgent`; a do 404 do 3.4 traz só `message` e `status`.

## E4 — Excluir (`DELETE /resume/{email}/language/portuguese`)

- [ ] 4.1 **Excluir um currículo ativo**: **Excluir** → confirmação "Todos os dados do seu currículo serão apagados de vez, sem como recuperar. Tem certeza de que deseja excluir o currículo? Atenção: só é possível excluir o currículo uma única vez ao dia." → **Sim, excluir**. Registro `exclusion` em `vis_resume_daily_action`. Esperado: `DELETE` → 200; toast "Currículo excluído" com "Todos os dados do seu currículo foram apagados."; faixa cinza sem botões; **todas as abas vazias**; nada em `vis_resume` nem em `vis_inactive_resume`; o hash sai de `emails` do LinkedIn (o registro some se era o único); grupos removidos; e-mail `...DeletedResume.html`.
- [ ] 4.2 **Excluir um currículo inativo**: com outro candidato (ou com o dia liberado), inative e depois exclua. Esperado: o mesmo do 4.1.
- [ ] 4.2b **Excluir, cadastrar e excluir de novo** (desde 2026-11-07): depois do 4.1, cadastre de novo (salva direto, sem confirmação: cadastrar não tem limite) e clique **Excluir**. Esperado: aviso "Limite diário atingido", sem confirmação nem `DELETE`; sem a marca do navegador, `DELETE` → 429 e o currículo continua salvo.
- [ ] 4.3 **Desistir na confirmação**: **Excluir** → **Não**. Esperado: nenhuma requisição; nada muda.
- [ ] 4.4 **Depois de excluir**: avance pelas abas vazias. Esperado: o salvar exige preencher tudo de novo (o formulário não guarda os dados apagados).
- [ ] 4.5 **Sessão expirada**: encerre a sessão no servidor como no 2.6 e clique **Excluir** → **Sim**. Esperado: 401, modal de login; depois de logar, a exclusão é refeita (200).

---

## Resumo do que este roteiro cobre

| Regra | Cenário |
|---|---|
| Leitura ao abrir: sem login e sessão inválida com a faixa "não está logado" e o link de login; sem currículo, ativo e inativo | 1.1 a 1.5 |
| Uma atualização, uma inativação, uma reativação e uma exclusão por dia: aviso pela marca do navegador e 429 do backend; cadastrar sem limite | 2.3c, 3.2b, 4.2b |
| Confirmação da atualização e "Salvar dados" verde nas abas da edição | 2.3, 2.3b |
| Faixa de situação com os botões certos para cada situação | 1.3 a 1.5, 3.1, 3.2, 4.1 |
| Salvar: inclusão, atualização, tipos sem habilidades, reativação pelo salvar | 2.1, 2.3 a 2.5 |
| Validações da tela antes do salvar; home office × regiões com aviso | 2.7, 2.8 |
| LinkedIn compartilhado e devolvido (lista de e-mails) | 2.9, 2.10 |
| Inativar, reativar, desistir, 404 de outra aba | 3.1 a 3.4 |
| E-mail do currículo inativado: aviso de que deixou de ser visto, link para reativar e tabela de como os recrutadores o viam | 3.1b |
| Excluir ativo e inativo, desistir, formulário limpo | 4.1 a 4.4 |
| 401 nas ações: modal de login e refazer | 2.6, 3.5, 4.5 |
| Respostas sem os dados da sessão | 1.6, 2.2, 3.6 |
| E-mail ao candidato em cada ação | 2.1, 3.1, 3.2, 4.1 |
| E-mail do currículo salvo: confirmação, próximo passo, tabela de uma linha sem datas, link ao formulário | 2.11 |
| Habilidades depois da 15ª e regiões depois da 3ª fora do e-mail, contadas por link com `title` | 2.12 |

---

## Execução de 2026-10-15

Ambiente: Elasticsearch local, APIs jn e vis fora do Eclipse (código com as decisões 1a, 2a, 3b, 4a, 5a e os achados 28 e 29), front em `npm run dev`. As capturas de tela do Chrome não funcionaram (janela oculta); tudo foi conferido pelo DOM, pelas requisições registradas na página, pelo Elasticsearch e pelos arquivos de e-mail em `C:\logs\email`.

| Passo | Resultado | Observação |
|---|---|---|
| 1.1 | ✔ | nenhuma chamada às APIs, sem faixa e sem modal |
| 1.2 | ✔ | `GET` 401 em silêncio |
| 1.3 | ✔ | 200 sem registro; faixa cinza sem botões |
| 1.4 | ✔ | faixa verde com Inativar e Excluir; abas preenchidas; "5 Habilidades" sem colar o texto |
| 1.5 | ✔ | faixa laranja com Reativar e Excluir |
| 1.6 | ✔ | sem `sessionToken`, `ip` e `userAgent`; mas a resposta traz a lista interna `hash` (achado R05-2) |
| 2.1 | ✔ | toast com o detalhe novo; `vis_resume_linkedin` com um hash; e-mail `SavedResume` |
| 2.2 | ✔ | resposta só com campos do currículo |
| 2.3 | ✔ | um registro, função nova, 16 habilidades mantidas |
| 2.4 | ✔ | tipos 2, 3 e 4 sem `skills/fromText`; empresa de 21 caracteres pelo autocomplete (decisão 1a) |
| 2.5 | ✔ | salvar o inativo reativou |
| 2.6 | ✔ | 401 → login com senha → salvar refeito (200) |
| 2.7 | ✔ | LinkedIn com hífen, empresa de 51, experiência 71, temporário 13, sem CLT/PJ: botão desabilitado e mensagem certa |
| 2.8 | ✔ | avisos "Regiões desmarcadas" (com a contagem) e "Home office desmarcado"; sem aviso quando nada é desfeito; salvar com `ddd: [10]` → 200 |
| 2.9 | ✔ | dois hashes em `emails`; a entrega do aviso no Telegram real deve ser conferida no chat do operador |
| 2.10 | ✔ | o endereço emprestado ficou só com o dono original (decisão 2a) |
| 3.1 | ✔ | inativado pela primeira aba (decisão 5a); só em `vis_inactive_resume`; 3 grupos inativos; e-mail `DeactivatedResume` |
| 3.2 | ✔ | reativado; ao lado de "Salvar dados" só o voltar; e-mail `ReactivatedResume` |
| 3.3 | ✔ | "Não" não chama nada |
| 3.4 | ✔ com ressalva | 404 e a tela releu a situação, mas o formulário continuou com o currículo apagado e nada foi dito ao candidato (achado R05-1) |
| 3.5 | ✔ com ressalva | 401 → login → inativação refeita; antes, o modal reaproveitou um 409 de conflito guardado no `localStorage` de uma tentativa anterior (achado R05-3) |
| 3.6 | ✔ | 404 com só `{"message":"NOT_FOUND","status":"NOT_FOUND"}` (decisão 3b) |
| 4.1 | ✔ | toast novo; abas vazias; nada no ES, no LinkedIn nem nos grupos; e-mail `DeletedResume` |
| 4.2 | ✔ | inativo excluído |
| 4.3 | ✔ | "Não" não chama nada |
| 4.4 | ✔ | avançar desabilitado com as abas vazias |
| 4.5 | ✔ | 401 → login → exclusão refeita |

### Achados da execução

| # | Lado | Sintoma | Esperado | Gravidade | Situação |
|---|---|---|---|---|---|
| R05-1 | front | Depois do 404 de Inativar/Reativar (currículo excluído em outra janela), a faixa passa a "Você ainda não tem currículo salvo", mas as abas continuam com os dados apagados e nenhum aviso aparece; "Salvar dados" recriaria o currículo | Limpar as abas como no Excluir e avisar o candidato | baixa | **corrigido** (decisão a) |
| R05-2 | back | `GET /resume/{email}` devolve a lista `hash` (45 chaves internas de agrupamento, que a tela não usa) | Devolver só os campos que a tela usa | baixa | **corrigido** (decisão a): sem `hash` e `email` |
| R05-3 | front (modal de login, jn) | O modal guarda no `localStorage` (`logins`) o 409 "já há um login corrente" e o reaproveita sem perguntar ao servidor; quando aquela sessão já acabou, o candidato cai em "Desbloqueie seu login" (token por e-mail) em vez de digitar a senha | Conferir o conflito no servidor a cada vez | média | **corrigido** (decisão a): 409 fora do cache |
| R05-4 | back | `VisServiceResume.ChangeStatus` faz dois `exists` (principal e gêmea): fere a regra FSED registrada hoje | Uma leitura só, pela fluent interface | — | **corrigido**: `CcpGetEntityId` |

## Execução de 2026-10-26

Ambiente: Elasticsearch local, APIs js (8082) e vis (8081) fora do Eclipse com a mensageria assíncrona, front em `npm run dev`. Conferido pelo DOM, pelo Network do Chrome, pelo Elasticsearch e pelos e-mails em `C:\logs\email\<e-mail>\`.

| Passo | Resultado | Observação |
|---|---|---|
| 1.1 | ✔ | sem faixa, sem modal |
| 1.2 | ✔ | `GET` 401 em silêncio, sem modal |
| 1.3 a 1.5 | ✔ | faixas cinza, verde e laranja com os botões certos |
| 1.6 | ✔ | sem `sessionToken`, `ip`, `userAgent` e sem `hash` (R05-2 corrigido) |
| 2.1 | ✔ | pela tela (roteiro 04, C1); e-mail `SavedResume` |
| 2.2 | ✔ | resposta só com campos do currículo |
| 2.3 | ✔ | um registro, função nova |
| 2.4 | ✔ | tipo 2 pela tela (sem aba Habilidades, nenhum `skills/fromText`, `skill: []`); tipo 4 pela API |
| 2.5 + 2.6 | ✔ | inativo, sessão encerrada, salvar → 401 → login com senha → salvar refeito → ativo |
| 2.7, 2.8 | ✔ | roteiro 04, C5 |
| 2.9, 2.10 | ✔ | pela API; aviso ao operador vai ao Telegram real |
| 3.1, 3.2 | ✔ | e-mails `DeactivatedResume` e `ReactivatedResume` |
| 3.3, 4.3 | ✔ | "Não" não chama nada |
| 3.4 | ✔ | 404; aviso "Currículo não encontrado — Seu currículo não existe mais: ele foi excluído em outra janela." e formulário limpo (R05-1 corrigido) |
| 3.5 | ✔ | 401 → login → inativação refeita |
| 3.6 | ✔ | 404 só com `message` e `status` |
| 4.1, 4.2 | ✔ | e-mail `DeletedResume`; registro do LinkedIn removido quando era o único |
| 4.4 | ✔ | avançar desabilitado com as abas vazias |
| 4.5 | ✔ | 401 → login → exclusão refeita |
