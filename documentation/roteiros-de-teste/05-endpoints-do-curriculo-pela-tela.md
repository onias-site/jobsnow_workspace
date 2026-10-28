# Roteiro 05 — Endpoints do currículo pela tela (`VisRestApiResume`)

**Pré-requisito:** [00-preparacao-do-ambiente.md](00-preparacao-do-ambiente.md) até o item 4 (Elasticsearch, APIs js 8082 e vis 8081, front 3000 e login).

> **Criado e executado em 2026-10-15**, no Chrome, com 10 candidatos novos (`roteiro05.*.593167@teste.com`) e o helper `automacao/08-tela-curriculo-helper.js`, que preenche as abas e clica nos botões de verdade. Resultado na seção [Execução de 2026-10-15](#execução-de-2026-10-15), no fim. Cobre só os quatro endpoints do controller `VisRestApiResume`, sempre a partir de uma ação do candidato na tela "Sobre mim" (`http://localhost:3000/meus-dados/sobre-mim`; até 2026-10-17, "Ver meu currículo" em `/portuguese-version/como-estou-indo/ver-meu-curriculo`).

> **Executado de novo em 2026-10-26** no Chrome, junto com o roteiro 04, com `roteiro03.20261026@teste.com` (duas abas) e, para o tipo 4 e o LinkedIn emprestado, `roteiro01b.20261026@teste.com` pela API. Todos os passos conferiram, inclusive as correções R05-1 (aviso e formulário limpo depois do 404) e R05-2 (sem `hash` no `GET`). Para provocar o 401 com o currículo na tela (2.6, 3.5, 4.5), a sessão foi encerrada no servidor (`DELETE /login/{email}/{sessionToken}` na 8082) deixando a da aba como estava: trocar o `sessionToken` por um inventado faz o login seguinte cair em "Desbloqueie seu login" (409), porque a sessão verdadeira continua sendo a corrente. Resultado na seção [Execução de 2026-10-26](#execução-de-2026-10-26). A sugestão de habilidade e a sugestão de ajuste de hierarquia (outros controllers) ficam fora: estão nos roteiros 01 e 02. As chamadas de apoio da tela (`skills/fromText`, `companies/search/autocomplete`) aparecem só porque a tela precisa delas para montar o currículo.

## Os quatro endpoints

| # | Endpoint | Serviço | O que a tela faz para chamá-lo | Respostas esperadas |
|---|---|---|---|---|
| 1 | `GET /resume/{email}` | `VisServiceResume.GetData` | abrir ou recarregar a tela | 200 com o registro debaixo de `vis_resume` (ativo) ou `vis_inactive_resume` (inativo), ou sem nenhum dos dois (sem currículo); 401 sem sessão, tratado em silêncio |
| 2 | `POST /resume/{email}/language/portuguese` | `VisServiceResume.Save` | **Salvar dados**, na última aba | 200 com só os campos do currículo; 422 se o corpo violar a regra de algum campo; 401 sem sessão (abre o modal de login e salva depois dele) |
| 3 | `DELETE /resume/{email}/language/portuguese/status` | `VisServiceResume.ChangeStatus` | **Inativar** ou **Reativar**, na faixa de situação | 200; 404 quando o currículo não existe mais (a tela relê a situação); 401 sem sessão (modal de login e refaz) |
| 4 | `DELETE /resume/{email}/language/portuguese` | `VisServiceResume.Delete` | **Excluir**, na faixa de situação | 200; 401 sem sessão (modal de login e refaz) |

## O que conferir fora da tela

| O que | Onde |
|---|---|
| Requisição e resposta | F12 → **Network**, filtro `resume` |
| Currículo ativo | `http://localhost:9200/vis_resume/_search?pretty` |
| Currículo inativo | `http://localhost:9200/vis_inactive_resume/_search?pretty` |
| E-mails do LinkedIn | `http://localhost:9200/vis_resume_linkedin/_search?pretty` (campo `emails`, com os hashes) |
| Agrupadores | `jn_grouper` (ativos) e `jn_inactive_grouper` (inativos), filtrando por `child` |
| E-mail ao candidato | `C:\logs\email\<e-mail>\com.vis.messages.VisMessages$VisNotifyUserAbout<Ação>Resume.html`, com `<Ação>` = `Saved`, `Deactivated`, `Reactivated` ou `Deleted` |

> O Elasticsearch mostra uma escrita só depois do refresh (cerca de 1 s): espere um instante antes de conferir.

## Massa

Use candidatos novos, um por cenário, para que um cenário não dependa do anterior: `roteiro05.<cenário>.<hora>@teste.com`. Abra a sessão de cada um pelo modal de login (roteiro 03) ou pela API js com o User-Agent do navegador, como faz `automacao/07-amostra-para-tela.mjs`, e ponha no `sessionStorage` (`login` = `{email, sessionToken}`).

---

## E1 — Ler o currículo ao abrir a tela (`GET /resume/{email}`)

- [ ] 1.1 **Sem login**: no Console, `sessionStorage.removeItem('login'); localStorage.removeItem('logins')` e recarregue. Esperado: nenhuma faixa de situação, formulário vazio, **nenhum modal de login**; no Network, nenhum `GET /resume` sai (o front barra antes de enviar, sem sessão).
- [ ] 1.2 **Sessão inválida**: ponha no `sessionStorage` um `login` com `sessionToken` inventado e recarregue. Esperado: `GET /resume` → 401; nenhuma faixa, **nenhum modal**.
- [ ] 1.3 **Candidato sem currículo**: logado, recarregue. Esperado: `GET /resume` → 200 sem `vis_resume` nem `vis_inactive_resume`; faixa cinza "Você ainda não tem currículo salvo", **sem botões**; formulário vazio.
- [ ] 1.4 **Currículo ativo**: recarregue depois do E2. Esperado: 200 com `vis_resume`; faixa verde "Currículo ativo: visível para os recrutadores" com **Inativar** e **Excluir**; as abas voltam preenchidas com o que foi salvo (no TI, a aba **N Habilidades** com as habilidades gravadas, sem precisar colar o texto).
- [ ] 1.5 **Currículo inativo**: recarregue depois do 3.1. Esperado: 200 com `vis_inactive_resume`; faixa laranja "Currículo inativo: oculto dos recrutadores" com **Reativar** e **Excluir**; abas preenchidas.
- [ ] 1.6 **A resposta não expõe a sessão**: no Network, a resposta do 1.4 não tem `sessionToken`, `ip` nem `userAgent`.

## E2 — Salvar (`POST /resume/{email}/language/portuguese`)

- [ ] 2.1 **Inclusão, tipo 1 (TI)**: aba Currículo: função buscada, última função, LinkedIn `https://www.linkedin.com/in/roteiro05-<hora>`, uma empresa pelo autocomplete e outra digitada + Enter, tipo "Tecnologia da Informação" e o texto do currículo (com JAVA e SPRING BOOT). Avance por Idiomas, Habilidades, Opções (uma região, experiência, disponibilidade, temporário) e Salários (CLT). **Salvar dados**. Esperado: `POST` → 200; toast "Currículo salvo com sucesso" com o detalhe "Seu currículo está ativo e visível para os recrutadores."; faixa verde com **Inativar** e **Excluir**; `vis_resume` com os campos; `vis_resume_linkedin` com o endereço e um hash em `emails`; e-mail `...SavedResume.html`.
- [ ] 2.2 **A resposta não expõe a sessão**: a resposta do 2.1 traz só campos do currículo (sem `sessionToken`, `ip`, `userAgent`).
- [ ] 2.3 **Atualização**: troque a função buscada, avance até Salários e salve. Esperado: 200; `vis_resume` com a função nova; continua um só registro.
- [ ] 2.4 **Tipos 2, 3 e 4**: com outro candidato para cada tipo, preencha e salve. Esperado: sem a aba Habilidades; nenhum `POST skills/fromText`; 200 e o registro com `skill` vazio.
- [ ] 2.5 **Salvar um currículo inativo reativa**: com o currículo inativo (3.1), mude um campo e salve. Esperado: 200; faixa verde; o registro sai de `vis_inactive_resume` e volta a `vis_resume`.
- [ ] 2.6 **Sessão expirada no salvar**: com a tela preenchida, encerre a sessão no servidor (Console: `fetch('http://localhost:8082/login/<email>/<sessionToken>', {method:'DELETE', headers:{'Content-Type':'application/json', sessionToken:'<sessionToken>', email:'<email>'}, body:'{}'})`, com os valores do `sessionStorage.login`) e clique **Salvar dados**. Esperado: `POST` → 401 e o modal de login abre; depois de logar, o salvar é refeito sozinho e responde 200.
- [ ] 2.7 **Validações da tela barram o salvar** (nada sai para o `POST`): LinkedIn terminado em hífen; empresa com mais de 50 caracteres; experiência 71; temporário 13; sem CLT nem PJ. Esperado: o botão da aba fica desabilitado, com a mensagem da regra.
- [ ] 2.8 **Home office e regiões**: marque três regiões e depois home office; depois marque uma região. Esperado: os avisos "Regiões desmarcadas — ... as 3 regiões escolhidas foram desmarcadas." e "Home office desmarcado — ..."; salvar com home office sozinho → 200 com `ddd: [10]`.
- [ ] 2.9 **LinkedIn de outro e-mail**: com um segundo candidato, salve com o LinkedIn do 2.1. Esperado: 200; `vis_resume_linkedin` com os dois hashes em `emails`; o operador recebe no Telegram (real) o aviso de LinkedIn compartilhado.
- [ ] 2.10 **Devolver o LinkedIn emprestado**: o segundo candidato troca para um LinkedIn próprio e salva. Esperado: 200; o endereço do 2.1 fica só com o hash do primeiro candidato.

## E3 — Inativar e reativar (`DELETE /resume/{email}/language/portuguese/status`)

- [ ] 3.1 **Inativar, sem sair da primeira aba**: **Inativar** na faixa → confirmação "Seu currículo deixará de aparecer para os recrutadores..." → **Sim, inativar**. Esperado: `DELETE .../status` → 200; toast "Currículo inativado" com o detalhe "Seu currículo não aparece mais para os recrutadores até que você o reative."; faixa laranja com **Reativar** e **Excluir**; registro em `vis_inactive_resume` e grupos em `jn_inactive_grouper`; e-mail `...DeactivatedResume.html`.
- [ ] 3.2 **Reativar**: **Reativar** → **Sim, reativar**. Esperado: 200; toast "Currículo reativado" com "Seu currículo voltou a aparecer para os recrutadores."; faixa verde; de volta a `vis_resume` e `jn_grouper`; e-mail `...ReactivatedResume.html`.
- [ ] 3.3 **Desistir na confirmação**: **Inativar** → **Não**. Esperado: nenhuma requisição; nada muda.
- [ ] 3.4 **Currículo excluído em outra aba**: abra a tela em duas abas com o mesmo candidato; exclua na primeira; na segunda, **Inativar** → **Sim**. Esperado: `DELETE .../status` → 404; a segunda aba relê a situação e mostra "Você ainda não tem currículo salvo", sem botões.
- [ ] 3.5 **Sessão expirada**: encerre a sessão no servidor como no 2.6 e clique **Inativar** → **Sim**. Esperado: 401, modal de login; depois de logar, a inativação é refeita (200).
- [ ] 3.6 **Resposta sem dados da sessão**: a resposta do 3.1 não traz `sessionToken`, `ip` nem `userAgent`; a do 404 do 3.4 traz só `message` e `status`.

## E4 — Excluir (`DELETE /resume/{email}/language/portuguese`)

- [ ] 4.1 **Excluir um currículo ativo**: **Excluir** → confirmação "Todos os dados do seu currículo serão apagados de vez..." → **Sim, excluir**. Esperado: `DELETE` → 200; toast "Currículo excluído" com "Todos os dados do seu currículo foram apagados."; faixa cinza sem botões; **todas as abas vazias**; nada em `vis_resume` nem em `vis_inactive_resume`; o hash sai de `emails` do LinkedIn (o registro some se era o único); grupos removidos; e-mail `...DeletedResume.html`.
- [ ] 4.2 **Excluir um currículo inativo**: inative e depois exclua. Esperado: o mesmo do 4.1.
- [ ] 4.3 **Desistir na confirmação**: **Excluir** → **Não**. Esperado: nenhuma requisição; nada muda.
- [ ] 4.4 **Depois de excluir**: avance pelas abas vazias. Esperado: o salvar exige preencher tudo de novo (o formulário não guarda os dados apagados).
- [ ] 4.5 **Sessão expirada**: encerre a sessão no servidor como no 2.6 e clique **Excluir** → **Sim**. Esperado: 401, modal de login; depois de logar, a exclusão é refeita (200).

---

## Resumo do que este roteiro cobre

| Regra | Cenário |
|---|---|
| Leitura ao abrir: sem login e sessão inválida em silêncio; sem currículo, ativo e inativo | 1.1 a 1.5 |
| Faixa de situação com os botões certos para cada situação | 1.3 a 1.5, 3.1, 3.2, 4.1 |
| Salvar: inclusão, atualização, tipos sem habilidades, reativação pelo salvar | 2.1, 2.3 a 2.5 |
| Validações da tela antes do salvar; home office × regiões com aviso | 2.7, 2.8 |
| LinkedIn compartilhado e devolvido (lista de e-mails) | 2.9, 2.10 |
| Inativar, reativar, desistir, 404 de outra aba | 3.1 a 3.4 |
| Excluir ativo e inativo, desistir, formulário limpo | 4.1 a 4.4 |
| 401 nas ações: modal de login e refazer | 2.6, 3.5, 4.5 |
| Respostas sem os dados da sessão | 1.6, 2.2, 3.6 |
| E-mail ao candidato em cada ação | 2.1, 3.1, 3.2, 4.1 |

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
