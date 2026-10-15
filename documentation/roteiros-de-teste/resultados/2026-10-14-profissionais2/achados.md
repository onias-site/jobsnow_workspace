# Achados: carga do profissionais2 na tela do currículo (2026-10-14)

Objetivo: achar incoerências e bugs no front e no back usando os 4135 currículos do índice legado `profissionais2`.
Os dados gravados são só resultado do trabalho, não são usados para nada.

- Dados de apoio (fora do git, com e-mails reais): `C:\logs\carga-profissionais2\` — `curriculos.jsonl` (corpo montado
  + origem de cada campo em `meta`), `resultados.jsonl` (salvamentos), `ciclo-de-vida.jsonl` (verificações), logs.
- Scripts (em `documentation/roteiros-de-teste/automacao/`): `04-prep-curriculos.mjs` (monta os corpos),
  `04-carga-de-curriculos.mjs` (salva pela API), `05-ciclo-de-vida-curriculos.mjs` (inativar, reativar, excluir,
  concorrência), `06-comparar-enviado-gravado.mjs` (enviado × gravado).

## Resumo da execução

| # | Etapa | Resultado |
|---|---|---|
| 1 | Recriar entidades (jn, vis, jb) e subir APIs 8080/8081 | ok |
| 2 | `prep` dos 4135 | 4135 corpos, todos aceitos pelas regras da tela; 0 falhas em `/skills/fromText` |
| 3 | Carga pela API | **interrompida em 174 de 4135** pelo achado 1 (salvar chegou a 230 s; previsão de mais de 5 h e milhões de grupos) |
| 4 | Enviado × gravado (174) | todos iguais, descontadas as conversões documentadas; as 2 diferenças vistas eram do critério de comparação (LinkedIn repetido) |
| 5 | Ciclo de vida pela API (casos 1 a 8) | 333 verificações, 0 falhas nos dados; as respostas HTTP da concorrência estão no achado 6 |
| 6 | Tela | 4 currículos preenchidos campo a campo (tipos 1, 2, 3 e 4; uma região; 67 regiões; somente home office) e salvos; recarga da tela, Inativar, Reativar e Excluir pelos botões; ok, salvo os achados abaixo |

## Achados

| # | Lado | Comparação | Sintoma | Esperado | Reprodução | Ocorrências | Gravidade |
|---|---|---|---|---|---|---|---|
| 1 | back | 8 (status × efeito, tempo) | Explosão combinatória do `hash` do currículo: cada currículo gera de 1 a 48.720 hashes (DDDs × habilidades × idiomas × demais campos exatos de `VisResumeHashCombinations`), média de 1.494. 174 currículos produziram 191.415 documentos em `jn_grouper`. O salvar foi de 2,5 s (p50 dos 25 primeiros) a 55 s (p50 dos currículos 150 a 175), com máximo de 230 s; a vazão caiu de 0,6 para 0,22 currículo por segundo; as gravações de grupo continuaram 7 minutos depois de parar o cliente. Sem a carga concorrendo, um currículo com 10 hashes salva em 0,5 s | Número de grupos por currículo limitado (ou crescendo de forma aditiva, não multiplicativa) e salvar em poucos segundos | `resultados.jsonl` (`saveMs` por ordem de gravação); pior caso: currículo de TI com 56 DDDs, 86 habilidades e 2 idiomas → 48.720 hashes | toda a carga | alta |
| 2 | back | 12 | A sessão expira na virada da hora, apesar do `expirationDate` de um mês: as sessões dos reservados `denis_1010_33@hotmail.com` (`LN3XFQ34`), `faturetovet@gmail.com` (`Y9NE70NI`) e `priscila.andrade83@yahoo.com.br` (`DDJYSAAD`), criadas às 14:52 com `expirationDate` 14/11/2026, passaram a dar 401 `invalidSession` depois das 15:00 (as duas últimas sem nenhum outro uso). `jn_login_session_validation` é `@JnEntityDisposable(timeOption = hourly)`. Na tela, a reativação devolveu 401 e abriu o modal de login. Pior: depois disso o login com a senha dá 409 `loginConflict` (o conflito sobrevive à sessão morta), e o usuário tem de refazer o fluxo do token. Parece regressão do defeito da virada da hora corrigido em 2026-10-13 | A sessão vale até o `expirationDate`; sem sessão viva, não há conflito | Criar sessão antes de hh:00, validar depois de hh:00 → 401; POST `/login/{email}` → 409. Controle: `virada.hora.21562@teste.com` / `67942T1M` criada às 15:07:26 (resultado das 16:00 na seção de pendências) | 3 de 3 | alta |
| 3 | back | 12 | Validar 3 vezes uma sessão legítima a partir de outro User-Agent (GET `/login/{email}/{token}` na 8080, 401 `invalidSession`) grava `jn_login_session_token_attempts` e bloqueia a **senha** (POST `/login` → 423 `lockedPassword`), enquanto a mesma sessão continua válida no User-Agent original (200). Na 8081 (GET `/resume`) as recusas não contam | Ou a sessão de outro User-Agent não conta tentativa (como a sessão vencida e a aba velha), ou o bloqueio derruba também a sessão; senha bloqueada com sessão viva é incoerente, e as duas APIs deveriam contar igual | Criar conta com UA A; 3× GET `/login/{email}/{token}` com UA B; GET com UA A → 200; POST `/login` → 423. E-mail de teste: `bloqueio2.30599@teste.com` | 2 reservados (`gabriela.alves2203@hotmail.com`, `mbpaulo@gmail.com`) bloqueados assim | alta |
| 4 | back | 12 | Na concorrência (duas trocas de situação ao mesmo tempo no mesmo currículo), os dados ficam coerentes, mas as respostas não: em 6 de 8 casos as duas respondem 200 e o efeito líquido é uma só inativação (dois avisos de "desativado" para uma mudança); em 1 caso uma das duas responde **500** (`CcpErrorJsonFieldNotFound`: `records.entity.vis_resume.id.<id>` ausente); em 1 caso responde **301** (o REDIRECT interno da gêmea vazando como status HTTP) | Uma das duas troca e a outra recebe 409 (ou as duas trocam em sequência); nunca 500 nem 301 | Caso 7 do `05-ciclo-de-vida-curriculos.mjs`: `ivani.2005@hotmail.com` [500, 200], `antonio.colombo@gmail.com` [200, 301] | 2 de 8 com status errado; 6 de 8 com 200 duplo | média |
| 5 | back | 8 | O tratador de exceção falha ao registrar o 500 do achado 4: a mensagem do erro (que inclui o json inteiro) passa do `stringMaxLength` de `message` em `JnEntityJobsnowError`, o handler lança `CcpJsonValidationError` ("Failure in @ExceptionHandler") e o erro original não fica gravado | Erro longo truncado e gravado | log da vis às 15:11:44 (`CcpRestApiExceptionHandlerSpring.handle`, linha 139) | 1 | média |
| 6 | back + front | 8 | Com a carga rodando, a inativação pela tela levou cerca de 5 minutos para responder (o registro já tinha ido para `vis_inactive_resume` antes), e a tela fica só "carregando", sem retorno | Ação do usuário respondida em poucos segundos ou feita de forma assíncrona com retorno imediato | Inativar pela tela enquanto o `04-carga-de-curriculos.mjs` roda | 1 de 1 | média (consequência do achado 1) |
| 7 | back | 12 | Respostas que não são de login devolvem um campo `sessionToken` aleatório, que não é sessão válida: o 409 `loginConflict` (um novo a cada chamada), o 200 do envio do token (`origin: CreateLoginToken`) e o 429 `statusAlreadySentToken`, este para quem não se autenticou, junto com `timestamp`, `expirationDate` e `dateItWasSaved` da conta | Respostas de conflito, de envio de token e de token já enviado sem `sessionToken` nem datas da conta | POST `/login/thonvox@gmail.com/token/language/portuguese` duas vezes na mesma hora → 429 com `sessionToken`; GET `/login/{email}/{esse token}` → 401 | sempre | média |
| 8 | back | 12 | Senha bloqueada responde com status diferente conforme o endpoint: 427 em POST `/login/{email}/token` (CreateLoginEmail) e 423 em POST `/login/{email}` (ExecuteLogin), os dois com `status: lockedPassword` | Mesmo status HTTP para o mesmo `status` de negócio | Conta do achado 3 | sempre | média |
| 9 | back | 1 | `/skills/fromText` transforma o texto "Spring Boot" na habilidade `SPRINGBOOT DEVTOOLS` (rótulo `SPRING BOOT (SPRINGBOOT DEVTOOLS)`): DevTools é um módulo do Spring Boot, não sinônimo dele | `SPRING BOOT` como habilidade própria | POST `/skills/fromText` `{"text":"Desenvolvedor Java com Spring Boot","excludedSkill":[]}` | todo currículo que cita Spring Boot | média |
| 10 | front × back | 1 | O backend aceita `ddd` com home office (10) e regiões juntos (`[10, 11]` → 200), mas a tela não deixa montar isso (escolher uma região desmarca o home office e vice-versa); ao carregar esse currículo, a tela mostra os dois marcados, um estado que ela mesma não cria | Mesma regra nos dois lados: ou o backend recusa 10 junto com regiões, ou a tela permite | POST `/resume/priscila.andrade83@yahoo.com.br/language/portuguese` com `ddd: [10, 11]` → 200; recarregar a tela | sempre | média |
| 11 | back | 12 | A resposta do salvar ecoa o corpo com `sessionToken`, `ip` e `userAgent` | Resposta sem dados da sessão | POST `/resume/{email}/language/portuguese` | sempre | baixa |
| 12 | back | 12 | GET `/resume/{email}` sem corpo responde 400 (o controller exige `@RequestBody` num GET); a tela só funciona porque o `JnAjax` monta a chamada de um jeito que contorna isso | GET sem corpo funcionando | `fetch('http://localhost:8081/resume/{email}', {headers: {sessionToken, email}})` → 400 | sempre | baixa |
| 13 | front | 10 | Ao avançar da aba Currículo, a tela chama POST `/skills/fromText` com texto vazio até para currículo que não é de TI (tipo 4 no teste) | Chamar as habilidades só para o tipo 1 | Tipo "nível operacional" → avançar | sempre | baixa |
| 14 | front | 10 | Depois de "Excluir" (que apaga tudo de vez), o formulário continua preenchido com os dados apagados, e um clique em "Salvar dados" recria o currículo | Limpar as abas depois da exclusão | Excluir pela tela e olhar as abas | sempre | baixa |
| 15 | front | 10 | Com "qualquer estado / cidade" marcado, o rótulo diz "68 Regiões selecionadas"; são 67 regiões (a própria opção entra na conta) | "67 regiões" ou "Qualquer estado / cidade" | Aba Opções → marcar "qualquer estado / cidade" | sempre | baixa |
| 16 | front | 10 | A lista de idiomas (47 itens) não tem busca e vem ordenada pelo `id` (Inglês, Mandarim, Hindi, Espanhol...), não em ordem alfabética | Filtro por texto e ordem alfabética | Aba Idiomas → abrir a lista e digitar | sempre | baixa |
| 17 | front | 2 | As mensagens da aba Opções dizem "devem estar entre 1 e 70" (experiência), "entre 1 e 30" (disponibilidade) e "entre 1 e 12" (temporário), mas 0 é aceito pelos dois lados (é o valor do checkbox) | Mensagem coerente com a regra | `FormFilter.tsx:60-62` | sempre | baixa |
| 18 | front + back | 9 | Empresa que não está na base volta do autocomplete como o próprio texto em maiúsculas ("SICREDI", "CLINICA PET ZYXW") e grava assim, enquanto a que está na base grava com a grafia da base ("Santander", "Capgemini"); Enter não adiciona a empresa, só o clique na sugestão | Grafia única e Enter adicionando | Aba Currículo → empresas → digitar "Sicredi" | sempre | baixa |
| 19 | back | 3 | O backend aceita o mesmo `linkedinAddress` para candidatos diferentes e slug terminado em hífen (`https://www.linkedin.com/in/andre-`, comum quando o texto do PDF quebra a linha) | Avisar ou recusar LinkedIn de outro e-mail | 41 LinkedIns repetidos no `curriculos.jsonl` (parte veio do `prep`) | 41 | baixa |

## O que funcionou como esperado

| # | Verificação | Resultado |
|---|---|---|
| 1 | Corpo enviado × gravado (174 currículos): DDDs, idiomas sem `id`, experiência como ano de início, pretensões, habilidades por `type`/`category` | igual |
| 2 | Tela × API para o mesmo currículo de TI (`cleiton.greco@hotmail.com`): habilidades, implícitas e campos | igual |
| 3 | Recarga da tela (`loadFromSavedResume`) nas 4 abas, inclusive 67 regiões → "qualquer estado" | igual ao salvo |
| 4 | Inativar, reativar, salvar inativo, excluir ativo e inativo: entidade principal/gêmea, grupos principais/gêmeos e e-mail de aviso | 333 de 333 |
| 5 | Status e exclusão de quem não tem currículo | 404 e 200/404 como esperado |
| 6 | Validação da tela nos limites (temporário 13 desabilita o avançar) | ok |

## Pendências

| # | Situação atual | Opções | Minha recomendação |
|---|---|---|---|
| 1 | Carga parada em 174 de 4135 por causa do achado 1 | resolvido: achado 1 corrigido e recarga completa (seção "Recarga completa após o reset") | - |
| 2 | Sessão de controle `virada.hora.21562@teste.com` / `67942T1M` (15:07:26, 200 na criação, sem outro uso) | validada às 16:00:47 | **401 `invalidSession`**: achado 2 confirmado (4 de 4); corrigido |
| 3 | Perfil terminado em hífen nos 20 que não deu para reconstituir | decisão do usuário (2026-10-15): manter a regex (os erros provaram que a validação funciona) e inventar o LinkedIn desses 20 na carga | feito: 11 salvos, 9 com 409 de sessão aberta tentados a cada 5 min (`C:\logs\carga-profissionais2\linkedin-inventado\`) |
| 4 | Mesmo LinkedIn em e-mails diferentes (2ª metade do achado 19) | decisão do usuário: aceitar e avisar o suporte. Exige entidade nova `vis_resume_linkedin` (PK `linkedinAddress`, campo `email`), lida por id no salvar, porque a OQL proíbe procurar o LinkedIn em `vis_resume` no online | feito (2026-10-15): `VisEntityResumeLinkedin` (`vis_resume_linkedin`, PK `linkedinAddress`, `email` em hash); `VisBusinessResumeLinkedinOwner` depois do save (endereço novo: insere calado; mesmo e-mail: nada; outro e-mail: atualiza e o `afterUpdate` manda `VisNotifySupportAboutSharedLinkedin` ao operador do bot); `VisBusinessResumeLinkedinRelease` antes do save (troca de endereço) e do delete-anywhere libera o endereço antigo só se ainda for deste e-mail; inativar mantém. Regex do LinkedIn centralizada em `VisJsonCommonsFields`. Aviso repetível: sem isso, 4 currículos com o mesmo endereço salvando juntos (`ResumeGroupersConcurrencyTest`) corriam entre a checagem de "já enviado" e o registro do envio e o bulk terminava em `JnErrorReprocessInfiniteLoopPrevented`. Testes: `ResumeLinkedinOwnerTest` (5) e os 54 do vis verdes. Índice criado e template semeado sem recriar o vis; os currículos gravados antes de 2026-10-15 não têm par (sem produção, o reset resolve) |
| 5 | Achado 6 (inativar levava 5 min durante a carga) | dependia do achado 1, já corrigido | medir de novo na próxima carga |

## Rodada de correções (noite de 2026-10-14)

| # | Achado | Situação | Prova |
|---|---|---|---|
| 1 | Explosão de hashes | corrigido: `ddd` fora de `VisEntityVirtualHashGrouper`, de `VisResumeHashCombinations` e de `VisJsonHashCombinationFields` | 225 currículos novos: hashes p50 118, máx 1.900 (antes máx 48.720); salvar p50 3,6 s, p90 6,6 s, máx 48 s, 0,66/s com 8 em paralelo (antes p50 até 55 s, máx 230 s) |
| 2 | Sessão morria na virada da hora | corrigido: `JnDisposableEntity.getRecordFromUnionAll(unionAll, Supplier)` só lia o documento do período e ignorava a cópia; o `currentSessionTokenHash` do conflito (também `hourly`) sumia na virada | 13 testes de descartáveis (todas as granularidades em uso) falham sem a correção e passam com ela; `ValidateLogin.sessionSurvivesTheTurnOfTheHourWhileItsCopyIsValid`; ao vivo: sessão de 20:16 deu 200 às 21:00:50 |
| 3 | Outro User-Agent bloqueava a senha | corrigido: `JnBusinessRefuseSessionOfAnotherClient` recusa (401) sem contar tentativa o token da sessão corrente vindo de outro cliente | teste novo falha sem e passa com; HTTP: 4× outro UA = 401, UA original 200, login 409 (não 423) |
| 5 | Handler falhava com mensagem longa | `JnJsonCommonsFields.message` de 500.000 para 50.000.000 | - |
| 10 | Home office + regiões | corrigido: `VisJsonValidatorHomeOfficeAlone` em `VisEntityResume.Fields` | HTTP `[10, 11]` → 422 com a mensagem; testes do validador e do serviço |
| 11 | Salvar ecoava a sessão | corrigido: Save, Delete e ChangeStatus devolvem só os campos do currículo | `ResumeServiceTest.theAnswersDoNotEchoTheSessionValues`; HTTP sem `sessionToken`/`ip`/`userAgent` |
| 12 | GET sem corpo → 400 | corrigido: o `CcpPutSessionValuesRequestWrapper` declara `application/json` quando a requisição não tem `Content-Type` | `PreparedBodyContentLengthTest`; HTTP GET sem corpo → 200 |
| 13 | `/skills/fromText` fora de TI | corrigido no front: só o tipo 1 chama | tela: tipo 4 avança sem requisição |
| 14 | Formulário cheio após Excluir | corrigido no front: stores das abas voltam ao estado inicial e as abas são remontadas (`formVersion`) | tela: após excluir, aba Currículo e campos vazios |
| 20 | Novo: cache local quadrático | corrigido: `CacheMap` copiava o mapa inteiro (`CcpJsonRepresentation` imutável) a cada put/delete sob trava global; marcas de exclusão com trava por chave | jstack com 7 threads presas em `CacheMap`; salvar com 8 hashes levava 12 s |
| 17 | Mensagens "entre 1 e N" | retirado: 0 no campo é o próprio checkbox (`checked={value == 0}`), a mensagem vale para o campo de texto | - |

## Segunda rodada: decisões do usuário (noite de 2026-10-14)

| # | Decisão | O que mudou | Prova |
|---|---|---|---|
| 4 | a | `VisServiceResume.ChangeStatus`: REDIRECT e `CcpErrorJsonFieldNotFound` causados por outra troca simultânea viram 200 (a troca já aconteceu) | caso 7 do `05-ciclo-de-vida-curriculos.mjs` (`CASOS=7`, filtro novo): 8 pares, todos [200, 200], dados coerentes (16 de 16); não dá para garantir que a corrida caiu no caminho do 301/500 desta vez (antes, 2 de 8). Os 8 currículos ficaram inativos |
| 7 | a | `ExecuteLogin` recusado não devolve o `sessionToken` gerado antes das checagens; `CreateLoginToken`, `ResendLoginToken` e `UnlockLoginToken` não listam mais `sessionToken`. As datas ficam: o front as mostra ("token enviado em…, expira em…") e são do token, não da conta | `ExecuteLogin.refusedLoginDoesNotAnswerASessionToken` |
| 8 | a | `lockedPassword` 423 em `CreateLoginEmail`, `ExistsLoginEmail` e `SaveAnswers`; front (`ServerRequests.ts`) e OpenAPI ajustados. A OpenAPI do login listava "senha errada" como 423; corrigido para 427 | `JnProcessStatusEnumsTest.lockedPasswordIs423InEveryEndpoint` |
| 9 | a | `documentation/jn/skills/synonyms.json`: `SPRINGBOOT DEVTOOLS` sem "SPRING BOOT"/"SPRINGBOOT"/variantes; `SPRINGBOOT` sem as variantes de DevTools | `vis_skill` semeado de novo no reset |
| 15 | b | rótulo das regiões conta sem o `'0'` | tela: "qualquer estado / cidade" marca 68 itens e o rótulo mostra "67 Regiões selecionadas" |
| 16 | a | idiomas em ordem alfabética (`localeCompare` pt-BR) e `filter` com "Digite o idioma que você procura" | tela: a lista começa por Alemão, Amárico, Árabe, Azerbaijano; "ingl" deixa só Inglês |
| 18 | a | o controller não converte para maiúsculas; o serviço usa maiúsculas só na chave do grupo das 3 iniciais; Enter adiciona o texto digitado (`onKeyUp`) | `ResumeServiceTest.companyOutOfTheBaseKeepsTheTypedSpelling`; tela: a sugestão mantém "Minha Empresa Xpto" como digitado e o Enter adiciona o texto e limpa o campo |
| 19 | a | regex do LinkedIn (back e front): o perfil não termina em hífen | `ResumeServiceTest.linkedinProfileEndingWithAHyphenIsRefused`; 169 dos 4135 do `profissionais2` passam a receber 422 |
| - | cache | só `JnEntityGrouper` deixou de apagar chaves de cache (`JnDoNotDeleteKeysFromCache` no `@CcpEntityTwin` e nas escritas de `JnGroupers`). Defeito encontrado: `JnExecuteBulkOperation` ignorava a função de limpeza recebida e sempre usava `JnDeleteKeysFromCache`; passou a usar a recebida | recarga: cerca de 49 marcas de cache por currículo, antes centenas |

Reset: APIs paradas, `CcpCreateEntities` (jn, vis, jb) sem erro, pasta de marcas do cache local trocada por uma vazia (a antiga tinha 2,45 milhões de arquivos), APIs reiniciadas e recarga dos 4135 em `C:\logs\carga-profissionais2\recarga-2026-10-14\`.

Ajustes de teste: `ResumeLifecycleTest` usa uma habilidade única por execução (sem o ddd, o grupo de valores neutros é compartilhado com os currículos já gravados) e troca de grupo pela senioridade; `ResumeFieldTransformersTest` lê a senioridade como último campo.

## Recarga completa após o reset (2026-10-14, 22:13 a 23:50)

| Resultado | Currículos | Causa |
|---|---|---|
| Salvos | 3962 | - |
| 422 no LinkedIn | 169 | perfil terminado em hífen (decisão 19), esperado |
| 400 ao confirmar o e-mail | 4 | e-mail inválido na origem (`...@hotmail`, `eugênio...`, `null`, `...gmail.com.docx`), esperado |
| **Total** | **4135** | |

| Medida | Antes das correções | Após o 1 (225 currículos) | Recarga completa (3962) |
|---|---|---|---|
| Salvar p50 | até 55 s | 3,6 s | 2,5 s |
| Salvar p90 | - | 6,6 s | 5,7 s |
| Salvar p99 | - | - | 13,3 s |
| Salvar máx | 230 s | 48 s | 37,7 s |
| Vazão (8 em paralelo) | - | 0,66/s | 0,71/s (1h37 no total) |

Enviado × gravado (`06-comparar-enviado-gravado.mjs`, saída em `comparacao.json`): 3904 currículos comparados sem diferença em nenhum campo. O script passou a deixar de fora os 58 gravados cujo LinkedIn se repete no envio (41 endereços em 108 currículos; um deles, `https://www.linkedin.com/in/jo%C3%A3o-silva-123/`, aparece em 16): o casamento é pelo LinkedIn e comparava currículos de pessoas diferentes, o que gerou as 300 e poucas "diferenças" da primeira execução.

| # | Achado novo | Situação atual | Correção |
|---|---|---|---|
| 21 | 12 currículos gravados sem nenhum hash | `experience` aceita 0 a 70 (`maxValue = 70`), mas `VisSeniorityType.especialista(10, 70)` tem limite superior exclusivo: quem informa 70 anos não cabe em senioridade nenhuma, o produto cartesiano fica vazio e o currículo não entra em grupo algum (some da busca) | `especialista(10, 71)`; teste `ResumeFieldTransformersTest.theLongestExperienceAcceptedByTheValidationIsASpecialist` (falha com 70, passa com 71). Regravados pela carga (`C:\logs\carga-profissionais2\experiencia-70\`): 10 passaram a ter de 4 a 340 hashes; 2 receberam 409 `loginConflict` (sessão da recarga ainda aberta, regra de sessão única) e são tentados de novo a cada 5 min até a sessão vencer |

Os 169 recusados pelo LinkedIn não são defeito do sistema: o PDF do LinkedIn quebra a linha no hífen antes do código final do perfil (`www.linkedin.com/in/israel-lacerda-` + `b68489186 (LinkedIn)` na linha seguinte) e o `04-prep-curriculos.mjs` lia só a primeira linha. O prep passou a juntar a linha seguinte quando o perfil termina em hífen (e a usar a regex nova na checagem `frontAceita`).

| Recusados pelo LinkedIn | Currículos | Destino |
|---|---|---|
| Linha seguinte juntada, endereço válido | 149 | reenviados (`C:\logs\carga-profissionais2\linkedin-com-hifen\`): 50 salvos na hora, 99 com 409 `loginConflict` (sessão da recarga com menos de 1 h) tentados de novo a cada 5 min |
| Linha seguinte juntada, ainda inválido | 1 | `roberto-denis-` + `alves- castro-80a8b450`: duas quebras com espaço; fica recusado |
| Endereço completo terminado em `-/` no próprio texto | 4 | `matheusphilippe-/`, `paulosergioo-/`, `matheusalvessilva-/`, `eduardo-ribeiro--/`: parecem perfis reais terminados em hífen; ver decisão abaixo |
| Espaço no meio do endereço | 1 | `matheus- guimar%C3%A3es-lopes-86767516a/`; fica recusado |
| Sem texto do currículo no arquivo da carga | 14 | endereço inferido na preparação, sem como reconstituir; fica recusado |
| **Total** | **169** | |

Os 50 salvos de primeira tinham sessão aberta havia mais de 1 h e os 99 recusados, menos: confirma ao vivo a correção 2 (o `hourly` expira 1 h após a escrita, não na virada da hora).

| Decisão pendente | Situação atual | Opções | Minha Recomendação |
|---|---|---|---|
| Perfil terminado em hífen | a regex (decisão 19) recusa todo perfil terminado em hífen; 4 de 3626 currículos com texto trazem o endereço completo assim (`.../matheusphilippe-/`), com a barra final provando que não houve corte | a) manter a recusa; b) aceitar o hífen final quando vier seguido de `/` (o corte do PDF nunca traz a barra); c) voltar a aceitar qualquer hífen final | b: recusa os 156 cortes do PDF e aceita os 4 perfis aparentemente reais |

## Regressão completa após a recarga

| Execução | Testes | Falhas | Ignorados | Causa |
|---|---|---|---|---|
| 1ª | 2669 | 1 | 5 | `ResumeGroupersConcurrencyTest`: sem o ddd, os grupos de JAVA/JVM com os outros campos neutros são os mesmos dos currículos carregados (52 filhos em vez de 8) |
| Ajuste | - | - | - | o teste usa uma habilidade única por execução, confere só os seus currículos dentro de cada grupo e exige que os grupos exclusivos sejam apagados no fim |
| Classes afetadas de novo | 9 | 0 | 0 | `ResumeGroupersConcurrencyTest`, `ResumeLifecycleTest`, `ResumeFieldTransformersTest` |

## Madrugada de 2026-10-15 (a partir das 02:01)

### Regressão de partida

| Execução | Testes | Falhas | Erros | Ignorados | Tempo |
|---|---|---|---|---|---|
| `mvn -o test -pl ccp_rest-api-tests_jobsnow` às 02:01 | 2675 | 0 | 0 | 5 | 9 min 20 s |
| Depois do limite diário: `SkillSuggestionThroughSupportBotTest` + `SkillFixHierarchyThroughSupportBotTest` | 41 (2 novos) | 0 | 0 | 0 | 1 min 35 s |

### Automação pela tela (36 currículos, tudo pelo Chrome)

Helper `automacao/08-tela-curriculo-helper.js` injetado na página: preenche os campos pelos eventos do React e clica nos botões de verdade (Avançar, Salvar dados, Inativar, Reativar, Excluir e as confirmações), então cada requisição sai do código do front. Sessões abertas pela API jn com o User-Agent do Chrome (`07-amostra-para-tela.mjs`), conferência no ES por `09-conferir-tela-x-es.mjs`. Saídas em `C:\logs\carga-profissionais2\tela-2026-10-15\`.

| Tipo | Já carregados (update) | Novos (insert, LinkedIn inventado) | Salvos | Recarga confere | ES confere | Ciclo de vida |
|---|---|---|---|---|---|---|
| 1 (TI) | 12 | 2 | 14 ✔ | 14 ✔ | 14 ✔ | inativar/reativar 5, excluir 2, inativar/excluir 3 |
| 2 | 6 | 2 | 8 ✔ | 8 ✔ | 8 ✔ | inativar/reativar 2, excluir 3, inativar/excluir 1 |
| 3 | 6 | 1 | 7 ✔ | 7 ✔ | 7 ✔ | inativar/reativar 3, excluir 1, inativar/excluir 1 |
| 4 | 6 | 1 | 7 ✔ | 7 ✔ | 7 ✔ | inativar/reativar 3, excluir 1, inativar/excluir 1 |
| **Total** | **30** | **6** | **36** | **36** | **36** | Inativar 18, Reativar 12, Excluir 12: todos ok |

- O ES confere campo a campo: `desiredJob`, `lastJob`, tipo, PCD, viagens, negociável, disponibilidade, temporário, CLT/PJ/BTC, ano da experiência, DDDs, idiomas com nível, empresas (autocomplete e digitadas) e habilidades do TI; os excluídos sumiram das duas entidades.
- Salvar pela tela (do clique ao toast): p50 0,22 s, p90 1,3 s, máximo 1,9 s; TI p50 0,53 s.
- Endpoints exercitados pela tela: POST salvar (37), GET `/resume` (toda recarga), DELETE `/status` (30), DELETE excluir (12), GET `companies/search/autocomplete` (12 escolhas), POST `skills/fromText` (14), mais `skills/suggestion` e `/search` no modal.
- Casos de borda pela tela: experiência 71 trava o avançar ("entre 1 e 70") e 70 salva (grava 1956 e gera hashes, achado 21 segue corrigido); sem login a tela não mostra situação nem abre o modal; LinkedIn terminado em hífen trava a aba Currículo (o 27 da amostra trazia o original `.../in/mariana-`; refeito com o LinkedIn gravado); LinkedIn de outro e-mail salva e passa o dono em `vis_resume_linkedin` (aviso ao suporte enviado pelo Telegram real: confira no chat).
- Limite diário pela tela (candidato `tela.1792041421885.0@teste.com`): aviso nos dois modais antes do envio; 1ª sugestão (WAMP) "Sugestão enviada"; 2ª (ONENOTE) **"Limite diário atingido"** com o modal aberto; JAVA pela API com o dia gasto → 412 (a recusa sem custo vem antes); desistência da WAMP depois, para limpar o ticket.

### Achados da madrugada

| # | Lado | Sintoma | Esperado | Reprodução | Ocorrências | Gravidade | Situação |
|---|---|---|---|---|---|---|---|
| 22 | front | Recarregar um currículo de TI salvo quebrava em `item.parent is not iterable` (`getImplicitSkills`) e a aba Habilidades sumia: a aba não envia `parent` vazio, e a leitura esperava sempre um array | Aba Habilidades remontada com as habilidades gravadas | Abrir a tela com o candidato 30 depois de salvo; console | todo TI com habilidade sem conhecimento implícito | alta | **corrigido**: `toSkillListItem` normaliza `parent` (`SubMenuMyResume.tsx`); a aba "14 Habilidades" voltou na mesma tela |
| 23 | front + back | O autocomplete de empresas sugere nomes com mais de 20 caracteres ("Santibanezconsultores", "Transportadoraaricanduva"), que a própria tela recusa ("Cada empresa / consultoria deve ter de 2 a 20 caracteres") e trava o avançar | Só sugerir o que pode ser gravado, ou aceitar o que é sugerido | Aba Currículo → empresas → digitar "San" e escolher a primeira | 158 das 14.132 empresas da base; 9 das 12 listas abertas na automação | média | decisão 1 abaixo |
| 24 | back | O par de `vis_resume_linkedin` some quando quem tomou o endereço emprestado o devolve, embora o dono original continue com ele no currículo; um terceiro e-mail com o mesmo endereço já não avisa o suporte | O endereço continua com dono enquanto algum currículo o usar | Candidato 35 salva com o LinkedIn do 32, depois volta ao seu: `vis_resume_linkedin` sem `.../tela-1792041421885-2`, que segue no currículo do 32 | sempre que um endereço compartilhado é devolvido | média | decisão 2 abaixo |
| 25 | back | As respostas de erro de negócio (412, 409, 410, 429...) trazem em `message` o json inteiro da requisição, com `sessionToken`, `ip` e `userAgent` (o 11 tirou esses campos só das respostas de sucesso do currículo) | Erro sem os dados da sessão | POST `/resume/{email}/skills/suggestion` com `JAVA` → 412; `message` tem o `sessionToken` | todo `CcpErrorFlowDisturb` do jn e do vis | média | decisão 3 abaixo |
| 26 | front | Currículo de TI recarregado não tem o texto (não é gravado, por causa da LGPD), e o modal "Deixamos de listar alguma habilidade?" responde "Habilidade fora do currículo... não aparece no texto do seu currículo" para qualquer palavra: a mensagem culpa a palavra, quando falta o texto | Pedir para colar o texto do currículo na aba Currículo antes de sugerir | Recarregar o candidato 30 → aba Habilidades → sugerir WAMP | sempre depois de recarregar | média | decisão 4 abaixo |
| 27 | front | Inativar, Reativar e Excluir só aparecem ao lado de "Salvar dados", na última aba: para inativar o currículo, o candidato passa por todas as abas (com as validações de cada uma) | Botões da situação visíveis na tela inteira, junto da faixa de situação | Abrir a tela com currículo salvo: nenhum dos três botões na aba Currículo | sempre | baixa | decisão 5 abaixo |
| 28 | front | Home office e regiões se excluem em silêncio: marcar uma região desmarca o home office (e o contrário), sem aviso | Explicar a regra (o backend recusa os dois juntos desde o 10) | Aba Opções → marcar home office, depois São Paulo | sempre | baixa | registrar |
| 29 | front | Os toasts repetem o título no corpo: "Currículo salvo com sucesso Currículo salvo com sucesso", "Currículo excluído Currículo excluído" | Título e detalhe diferentes, ou só um | Salvar ou excluir pela tela | sempre | baixa | registrar |
| 30 | roteiro | O caso 7 (concorrência) do `05-ciclo-de-vida-curriculos.mjs` lia o ES logo depois das duas trocas, sem esperar o refresh, e acusava grupos dos dois lados ou de nenhum; relidos com calma, os 10 casos estavam coerentes | Esperar o refresh como os casos 1 a 5 | `CASOS=7 node 05-...` | 8 de 16, depois 7 de 16 | — | **corrigido** no roteiro: 16 de 16 |
| 31 | roteiro | `03-modal-de-login.mjs` esperava 427 na verificação do e-mail com a senha bloqueada; desde a correção 8 é 423 | 423 | L4 da automação | 1 de 106 | — | **corrigido** no roteiro; o L10 novo (sessão de outro User-Agent, login recusado sem `sessionToken`) entrou: 113 de 113 |

### Roteiros executados

| Roteiro | Como | Resultado |
|---|---|---|
| 00 | atualizado (tabelas novas, item 5A para liberar o dia, LinkedIn sem hífen final); comandos do 5A executados | ok: apagaram os registros do dia |
| 01 | suíte `SkillSuggestionThroughSupportBotTest` (15) + S10 pela tela e pela API | 15 de 15; S10 10.1 a 10.4 ok (10.5 não feito para não mandar outro aviso ao Telegram real) |
| 02 | suíte `SkillFixHierarchyThroughSupportBotTest` (26) + aviso do H12 no modal | 26 de 26; 12.1 ok; 12.2 a 12.5 cobertos pelo teste `onlyOneRequestPerDay`, não pela tela (cada envio vai ao Telegram real) |
| 03 | `03-modal-de-login.mjs` | 113 de 113 (depois do achado 31) |
| 04 (tela do currículo) | automação pela tela acima | 36 de 36 |
| 05 (ciclo de vida) | `05-ciclo-de-vida-curriculos.mjs ... 3` | casos 1 a 4: 93 de 93; caso 7: 16 de 16 (depois do achado 30); caso 8: 144 de 145 (o que falta é `onias85@gmail.com`, conta real com outra senha, esperado) |
| 06 (enviado × gravado) | `06-comparar-enviado-gravado.mjs` na recarga | 3892 comparados; diferenças explicadas: 11 empresas acrescentadas pela tela, 183 LinkedIns corrigidos/inventados nos reenvios, 1 e-mail com dois currículos no jsonl (`lucas.eschechola@gmail.com`, vale o último) |

### Decisões pendentes

| # | Situação atual | Opções | Minha Recomendação |
|---|---|---|---|
| 1 | Achado 23: 158 empresas da base do autocomplete têm mais de 20 caracteres (nomes colados, sem espaço: "Transportadoraaricanduva") e a tela recusa o que ela mesma sugere | a) subir o limite de `notAllowedCompany` para 50 no back e no front; b) o autocomplete deixa de devolver nomes acima de 20; c) truncar na escolha | a: são nomes reais; o limite de 20 corta empresas legítimas também digitadas à mão |
| 2 | Achado 24: o par do LinkedIn guarda um e-mail só; quem devolve um endereço emprestado apaga o par do dono original | a) o par passa a guardar o conjunto de e-mails (hash) que usam o endereço: salvar acrescenta, trocar/excluir tira só o próprio, aviso quando sobra outro e-mail; b) na liberação, devolver o par ao e-mail anterior (guardar só o anterior); c) aceitar a lacuna | a: cobre qualquer número de donos, escrita atômica por script como nos agrupadores |
| 3 | Achado 25: erro de negócio ecoa `sessionToken`, `ip` e `userAgent` em `message` (tratador genérico do ccp, vale para jn e vis) | a) o tratador tira os campos de sessão do json antes de montar `message`; b) `message` deixa de levar o json (só o status e os campos listados na exceção); c) manter | b: o front já usa `status` e os campos listados; o json inteiro na resposta também expõe o hash e campos internos. Exige conferir os callbacks que leem `message` |
| 4 | Achado 26: sem texto colado, toda sugestão de habilidade é recusada como "fora do currículo" | a) com o texto vazio, o modal avisa "cole o texto do seu currículo na aba Currículo para sugerir uma habilidade" e não deixa digitar; b) deixar o servidor validar contra as habilidades gravadas; c) manter | a: só o texto prova que a palavra consta no currículo, e a mensagem passa a dizer o que fazer |
| 5 | Achado 27: botões da situação só na última aba | a) levar Inativar/Reativar/Excluir para a faixa de situação, no topo, visível em todas as abas; b) manter | a |
| 6 | (de 2026-10-15, antes da madrugada) perfil do LinkedIn terminado em `-/` | a) manter a recusa; b) aceitar hífen final seguido de `/`; c) aceitar qualquer hífen final | b |

### Decisões do usuário (2026-10-15, tarde)

| # | Achado | Decisão | O que mudou | Prova |
|---|---|---|---|---|
| 1 | 23 | a | `notAllowedCompany` de 2 a **50** caracteres no back (`VisEntityResume`), no front (`FormResume.tsx`) e na OpenAPI; a busca do autocomplete (`VisServiceCompany`, campo `search`) também aceita até 50 | compilação; roteiro 04, 5.2 e 5.2b |
| 2 | 24 | a | `vis_resume_linkedin` guarda a lista `emails` (hashes) em vez de um `email`; salvar acrescenta e trocar/excluir tira só o próprio e-mail, por script atômico (`VisResumeLinkedinEmails`), e o registro some com o último; o aviso ao operador sai quando, depois de acrescentar um e-mail novo, a lista tem mais de um (envio direto, sem o decorator de update). Índice local recriado com o mapeamento novo | `ResumeLinkedinOwnerTest` 6 de 6, com o novo `givingBackABorrowedAddressKeepsItWithTheOriginalOwner`; `ResumeGroupersConcurrencyTest` verde |
| 3 | 25 | b | `CcpRestApiExceptionHandlerSpring`: no erro de negócio, `message` passa a ser o nome do status; a resposta leva só ele, `status` e os campos listados na exceção (o front não lia `message`) | `CcpRestApiExceptionHandlerSpringTest.aBusinessErrorDoesNotEchoTheRequestTest` |
| 4 | 26 | a | modal de sugestão de habilidade: sem texto do currículo, aviso no topo, campo da habilidade bloqueado e Enviar desabilitado | roteiro 04, 8.2 (não conferido na tela) |
| 5 | 27 | a | Inativar/Reativar/Excluir saíram de perto do "Salvar dados" e foram para a faixa de situação, visível em todas as abas | roteiro 04, C3 (não conferido na tela) |
| 6 | — | a | manter a recusa do perfil terminado em hífen (decidido antes, nesta data) | — |
| 7 | 29 | corrigir | os toasts de salvar, inativar, reativar e excluir (`SubMenuMyResume.tsx`) e o aviso de habilidade descartada (`TabSkills.tsx`) passaram a ter título curto e detalhe diferente; a automação da tela (`08-tela-curriculo-helper.js`) lê só o texto da faixa e não avança mais até a última aba para o ciclo de vida | roteiro 04, 1.4 (não conferido na tela) |
| 8 | 28 | a | `RegioesComponent.tsx`: marcar home office com regiões escolhidas avisa quantas foram desmarcadas; marcar uma região (ou "qualquer estado / cidade") com o home office marcado avisa que ele foi desmarcado; sem nada a desfazer, nenhum aviso | roteiro 04, 5.4 e 5.5 (não conferido na tela) |
