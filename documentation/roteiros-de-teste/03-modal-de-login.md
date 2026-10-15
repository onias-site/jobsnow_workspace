# Roteiro 03 — Modal de login

**Pré-requisito:** [00-preparacao-do-ambiente.md](00-preparacao-do-ambiente.md) até o item 3 (ambiente no ar e, de preferência, índices recriados).

> **Este roteiro foi executado de verdade no navegador em 2026-10-08** e **refeito em 2026-10-11** com a base recriada, de duas formas: pela automação da API com três candidatos intercalados (ver [Automação](#automação-da-api-com-candidatos-intercalados)) e no navegador com dois candidatos em duas abas, alternando tentativas (ver [L9](#l9--dois-candidatos-intercalados-no-navegador)). Cada texto "Esperado" abaixo foi visto na tela, no Network ou nos arquivos. Os poucos passos que **não** foram executados estão marcados como tal. Os bugs encontrados no caminho estão no fim, com o que foi corrigido.
>
> **Regra dos bloqueios:** a **3ª** senha errada seguida bloqueia a senha (`POST /login` → 429) e o **3º** token errado seguido bloqueia o token (`POST /password` → 429). O limite é a propriedade `maxAttempts` (3 se não estiver configurada). As tentativas são contadas **por e-mail**: o erro de um candidato nunca conta para outro, e um acerto zera só o contador de quem acertou.

> **Atualizado em 2026-10-15** (correções da campanha `profissionais2`): senha bloqueada responde **423** em todo endpoint (antes, a verificação do e-mail e as respostas do primeiro acesso davam 427); login recusado não devolve `sessionToken`, e os pedidos de token também não; o token da sessão corrente vindo de **outro navegador** (outro User-Agent) é recusado com 401 **sem contar tentativa** (antes, quatro tentativas assim bloqueavam a senha do dono); a sessão não cai mais na virada da hora. Veja L10.

## Como o modal funciona (resumo)

- **Não existe botão "Entrar".** O modal abre sozinho quando uma ação precisa de login e a API responde 401. Depois do login, a ação que pediu o login é **refeita sozinha**.
- Telas do modal, pela ordem em que aparecem:
  1. **"Diga quem é você, antes de continuar..."** — o e-mail (título "Trocar o e-mail" quando se volta a ela pelo link);
  2. **"Por favor, confirme o e-mail '...'"** — só no primeiro acesso;
  3. **"Informe suas preferências e objetivos"** — só no primeiro acesso;
  4. **"Criando uma nova senha"** / **"Refazer sua senha"** / **"Atualize sua senha"** / **"Desbloqueie a sua senha"** / **"Desbloqueie seu login"** — a mesma tela (senha + confirmação + token), com títulos diferentes conforme o motivo;
  5. **"Informe a senha para o login '...'"** — quem já tem senha.
- O token chega por e-mail. Localmente o e-mail vira arquivo: `C:\logs\email\com.jn.business.messages.JnMessages$JnNotifyUserAboutLoginToken.html` (procure "esse token é XXXXXXXX"; o arquivo é sobrescrito a cada envio, confira a hora).
- Os pedidos ao suporte (desbloqueio e reenvio do token) chegam como comando no arquivo `C:\logs\telegram\support-751717896.txt` (é o "Telegram" local da API jn).
- **Lentidão (corrigida em 2026-10-09):** na execução, login, gravação de senha e verificação de e-mail levavam de 5 a 10 segundos. A causa era BCrypt (cerca de 250 ms por hash) feito à toa em toda leitura das entidades de senha e de token. Agora a verificação de e-mail leva cerca de 50 ms e as leituras transformam só a chave primária, então o login leva cerca de 0,7 s (antes, 1 a 2 s): o que sobra é a conferência da senha, que é um BCrypt por natureza.

## Dados

- E-mail de teste: use um e-mail que **ainda não existe** (ex.: `roteiro.login@teste.com`). Não use o seu e-mail real: o roteiro bloqueia senha e token.
- Senhas: qualquer uma com 8+ caracteres, maiúscula, número e caractere especial (ex.: `Roteiro@2026`, `Roteiro@2027`...).
- Antes de começar: **F12 → Console** → `localStorage.removeItem('logins'); sessionStorage.removeItem('login')` (o navegador guarda respostas de login por e-mail e pode pular telas).
- **Vários candidatos ao mesmo tempo:** o arquivo do e-mail do token é **um só para todos os destinatários** e é sobrescrito a cada envio. Leia o token logo depois de cada envio e confira o e-mail dentro do arquivo (`...?email=<e-mail>&...`) antes de usar o token. Com o sandbox no ar, ele também escreve nesse arquivo (o `c:\logs` não é isolado).

## Automação da API com candidatos intercalados

`documentation/roteiros-de-teste/automacao/03-modal-de-login.mjs` faz pela API jn as mesmas chamadas do modal, alternando três candidatos novos a cada execução (A, B e C), e confere status, contador de tentativas, bloqueios, tokens e sessões. O papel do operador (`/solveLoginTokenTicket`) é feito por `automacao/SupportBotCommand.java`, que entrega o comando ao bot de suporte neste computador, sem Telegram (a resposta do bot vai para `C:\logs\telegram\support-751717896.txt` e o e-mail com o token novo para `C:\logs\email`).

- Pré-requisitos: ES 9200, API jn 8080 reiniciada depois de recriar os índices, e um `executaCcpCreateEntities.bat` já executado (ele gera `ccp_rest-api-tests_jobsnow\target\create-entities-args.txt`, o classpath usado pelo `SupportBotCommand`).
- Rodar, na raiz do workspace: `node documentation/roteiros-de-teste/automacao/03-modal-de-login.mjs`. Sai com código 1 se alguma verificação falhar e lista as falhas no fim. Não precisa recriar índices entre execuções.
- Comando do operador avulso (pasta `ccp_rest-api-tests_jobsnow`): `java @target/create-entities-args.txt ../documentation/roteiros-de-teste/automacao/SupportBotCommand.java /solveLoginTokenTicket unlockToken <email>`. No Git Bash, prefixe com `MSYS_NO_PATHCONV=1`, senão o `/solveLoginTokenTicket` vira um caminho de arquivo.

Ordem do que ela faz (cada passo alterna os candidatos):

| Cenário | O que é provado |
|---|---|
| L1 | e-mail novo 404 → confirmação 201 → preferências 202 → token 200 para os três; tokens diferentes; segundo envio 429 |
| Token errado | A erra 3 vezes (427 com `attempts` 1 e 2, depois 429) enquanto B erra 2 (inclusive com o token do A) e acerta, e C acerta de primeira; com o token bloqueado o A recebe 403 até com o token certo, na verificação do e-mail e no login; o B não é afetado |
| L3 | sair 200, sair de novo 404 |
| Senha errada | B erra 3 vezes (427, 427, 429) enquanto C erra 2 (inclusive com a senha do B) e acerta; senha certa do B bloqueado → 423; verificação do e-mail → 423 (era 427 até 2026-10-15); o acerto do C zera só o contador do C |
| Desbloqueio da senha | senha nova + token → 200; a senha antiga passa a contar do zero |
| Simultâneos | B e C erram e acertam a senha no mesmo instante: contadores e sessões separados; a sessão do C não vale para o B (401) |
| L7 | pedido de desbloqueio 200, repetido 409; o B (não bloqueado) recebe 404; operador resolve; o token novo chega por e-mail e na resposta do bot; novo pedido 404 ("não está bloqueado"); token antigo conta do zero; token novo → 200 |
| Um desbloqueio por dia | o A bloqueia o token de novo (3 erros, com um erro do B no meio) e o 2º pedido no mesmo dia recebe 429; nem a senha certa entra (403) |
| L8 | reenvio 200, repetido 409; operador resolve; reenvio depois de resolvido 429; o token anterior deixou de valer (427); o novo vale |
| L5 | login com outra sessão aberta, inclusive aberta por "Salvar senha" → 409; "desfazer o outro login" → 200, e a sessão nova também é login corrente (409 num novo login) |
| Sessões antigas | a sessão desfeita responde 401; usada mais vezes que o limite de tentativas, não bloqueia a senha; sair por ela responde 404 sem derrubar a sessão corrente; trocar a senha logado derruba a sessão anterior; sessões de outros e-mails não são afetadas |

**Resultado em 2026-10-11:** antes da correção, 95 de 98 verificações ok (as 3 falhas eram os bugs 3 e 7). Depois da correção, **106 de 106**.

## Como abrir o modal

1. Faça o item 5 da preparação (tela do currículo → **Idiomas** → aba **Habilidades**). Atenção: o 1º clique em **Idiomas** só valida o formulário (se faltar função ou LinkedIn, aparece "Falha!!! Deve-se informar ..." no canto); quando tudo está preenchido, ele lê o currículo.
2. Clique em **"Deixamos de listar alguma habilidade?"** e digite uma habilidade que **está escrita no texto do currículo** e **não está** na lista de habilidades encontradas (ex.: `Tecnologia da Informacao`, `Ingles avancado`). Uma habilidade que não aparece no texto é recusada ("Habilidade fora do currículo") e uma que já está na lista (ex.: `Kanban`) deixa os outros campos desabilitados. Saia do campo (Tab): só então **Sinônimos** e **Justificativa** são habilitados. Escreva uma justificativa com 10+ caracteres e clique em **Enviar**.
3. Sem login, abre **"Diga quem é você, antes de continuar..."**. A cada vez que precisar abrir o modal de novo, use outra habilidade do texto (uma sugestão já enviada abre só para leitura).

---

## L1 — Primeiro acesso (e-mail novo)

### Tela do e-mail
- [ ] 1.1 Esperado ao abrir: campo vazio, em vermelho "Favor informar um e-mail ao qual você tenha pleno acesso", **Avançar** desabilitado, rodapé "Informe o seu e-mail".
- [ ] 1.2 Digite `roteiro.login`. Esperado: "O e-mail 'roteiro.login' está em formato inválido", Avançar desabilitado, rodapé "Seja bem vindo ao seu primeiro acesso!!!".
- [ ] 1.3 Complete `roteiro.login@teste.com`. Esperado: a mensagem some, Avançar habilitado.
- [ ] 1.4 **Avançar**. Network: `HEAD /login/roteiro.login@teste.com/token` → **404** (e-mail ainda não existe).

### Confirmação do e-mail
- [ ] 1.5 Esperado: título "Por favor, confirme o e-mail 'roteiro.login@teste.com'", texto "Por favor, confirme o e-mail '...' para que possamos prosseguir com sua autenticação, ou corrija seu e-mail caso tenha digitado errado", **Confirmar** desabilitado, link "Clique aqui para trocar o e-mail".
- [ ] 1.6 Digite `outro@teste.com`. Esperado: "O e-mail 'outro@teste.com' informado nesta tela, não é o mesmo e-mail 'roteiro.login@teste.com' informado na tela anterior", Confirmar desabilitado.
- [ ] 1.7 Corrija para `roteiro.login@teste.com`. Esperado: mensagem some, Confirmar habilitado.
- [ ] 1.8 **Confirmar**. Network: `POST /login/.../token` → **201** (~3 s).

### Preferências
- [ ] 1.9 Esperado: "Informe suas preferências e objetivos" com "Como você nos conheceu?" (padrão "Por alguém ou por anúncio no linkedin"; opções linkedin, "Grupos de vagas no telegram", "Indicação de amigos", "outros") e "Qual seu objetivo?" (padrão "Salários e Empregos"; ou "Ver currículos").
- [ ] 1.10 Escolha "Grupos de vagas no telegram" e "Ver currículos" → **Enviar**. Network: `POST /pre-registration` → **202**.
- [ ] 1.11 Conferir: `http://localhost:9200/jn_login_answers/_search?pretty` tem `"channel":"telegram","goal":"recruiting"`.

### Criação da senha
- [ ] 1.12 Esperado: "Criando uma nova senha" com **Senha**, **Confirme a senha** e **Token recebido no e-mail '...'**. O token é pedido sozinho (`POST /token/language/portuguese` → **200**, ~5 s) e aparece "Seu token está sendo enviado ao e-mail '...' nos próximos minutos. Por favor, verifique sua caixa de entrada e sua caixa de spam / lixo eletrônico." Os links "Não recebeu ou perdeu o token? Clique aqui para reenviar" e "Clique aqui para trocar o e-mail" somem enquanto carrega e aparecem depois.
- [ ] 1.13 Com os três campos vazios, clique em **Salvar senha** (se estiver habilitado). Esperado: "Preencha a senha, a confirmação de senha e o token recebido por e-mail. A senha deve conter ao menos 8 caractéres, ...", **nada** no Network. *(Corrigido em 2026-10-08 — antes ia ao servidor, voltava 422 e a tela não dizia nada.)*
- [ ] 1.14 Validações (mensagem em vermelho, botão desabilitado):

| Faça | Esperado |
|---|---|
| Senha `fraca` | "A senha está inválida, ela deve conter ao menos 8 caractéres, ao menos uma letra maiúscula, ao menos um número e ao menos um caractere especial" |
| Senha `Roteiro@2026`, confirmação vazia | "Informe a confirmação de senha, ela deve conter ..." |
| Confirmação `Roteiro@2027` | "As duas senhas não são iguais" |
| Confirmação `Roteiro@2026`, token vazio | "Informe o token, ele deve conter exatamente 8 caracteres" |
| Token `ABC` | "Token não digitado corretamente, ele deve conter exatamente 8 caracteres" |

> Dica: ao digitar a senha, o painel de força ("Digite uma senha", "Senha difícil de descobrir"...) abre **por cima** do campo de confirmação. Tecle **Esc** antes de clicar na confirmação.

- [ ] 1.15 Token errado de 8 caracteres (`ZZZZZZZZ`) → **Salvar senha**. Network `POST /password` → **427** (~6 s). Esperado: "O token informado está incorreto, você ainda pode tentar mais 2 vez(es)" e o campo do token limpo.
- [ ] 1.16 Digite `ZZZZZZZZ` de novo. Esperado: "Este token já foi digitado antes e está incorreto, tente outro!" (sem ir ao servidor).
- [ ] 1.17 Token certo (do arquivo do e-mail) → **Salvar senha**. Network `POST /password` → **200** (~10 s). Esperado: o modal fecha, toast **"Sucesso!!! O usuário 'roteiro.login@teste.com' foi autenticado com sucesso!"** e, em seguida, **"Sugestão enviada"** (a ação que abriu o modal foi refeita).
- [ ] 1.18 Conferir: `http://localhost:9200/jn_login_token_attempts/_search?pretty` **não** tem tentativas pendentes para esse e-mail (o acerto zera as tentativas). *(Corrigido em 2026-10-08 — antes o erro do 1.15 ficava contando.)*

---

## L2 — Trocar a senha estando logado

- [ ] 2.1 Canto superior direito: clique no ícone do usuário (à direita da bandeira) → menu com **"Trocar Senha"** e **"Sair do Sistema"**.
- [ ] 2.2 **Trocar Senha**. Esperado: "Atualize sua senha" com "Preencha os campos para atualizar sua senha" e, logo depois, "**Seu token foi enviado ao e-mail '...' no dia DD/MM/AAAA - HH:MM e expirará no dia DD/MM/AAAA - HH:MM.**" (o token do primeiro acesso ainda vale; nenhum novo é enviado — `POST /token/language/portuguese` → **429**). *(Corrigido em 2026-10-08 — antes o 429 não era tratado e a tela ficava calada, sem dizer se o token tinha ido.)*
- [ ] 2.3 Senha nova + confirmação + **o mesmo token do L1** → **Salvar senha** → 200, toast "Sucesso!!! ... autenticado com sucesso!".
  > Observação: o token vale **um mês** e pode ser reutilizado dentro desse prazo; o toast diz "autenticado" mesmo sendo troca de senha.

## L3 — Sair do sistema

- [ ] 3.1 Menu do usuário → **Sair do Sistema**. Network `DELETE /login/{email}/{sessionToken}` → **200**. Toast "Sucesso!!! O usuário '...' encerrou o login com sucesso!".
- [ ] 3.2 Menu do usuário → **Sair do Sistema** de novo (sem login). Toast "Erro!!! Usuário não logado!!!". O mesmo vale para **Trocar Senha** sem login.

## L4 — Login de quem já tem senha (e bloqueio da senha)

- [ ] 4.1 Abra o modal (outra habilidade de teste). Digite o e-mail. Esperado: rodapé "Você já esteve aqui conosco, obrigado pelo retorno!!!".
- [ ] 4.2 **Avançar** → `HEAD /token` → **200** → "Informe a senha para o login '...'", com "Esqueceu sua senha? Clique aqui!" e "Clique aqui para trocar o e-mail". O botão **Login** começa **desabilitado**. *(Corrigido em 2026-10-08 — antes vinha habilitado com a senha vazia e o clique terminava num 422 mudo.)*
- [ ] 4.3 Senha errada `Errada@111` → **Login** → `POST /login/{email}` → **427** (~6 s). Esperado: "A senha informada está incorreta, você ainda tem direito a 2 tentativa(s)", campo limpo.
- [ ] 4.4 Digite `Errada@111` de novo. Esperado: "Esta senha já foi digitada antes e está incorreta, tente outra senha!" (a tela registra a tentativa no envio, antes da resposta).
- [ ] 4.5 `Errada@222` → "... você ainda tem direito a 1 tentativa(s)".
- [ ] 4.6 `Errada@333` → `POST /login` → **429**. Esperado: tela **"Desbloqueie a sua senha"** com "Devido a tentativas de acessos suspeitos, sua senha foi preventivamente bloqueada. Preencha os campos acima, para desbloqueá-la." e a mensagem do token ainda válido (como no 2.2). *(Visto em 2026-10-11: as duas frases saem coladas com ponto duplo, "desbloqueá-la.. Seu token foi enviado...". É só texto.)*
- [ ] 4.6b Com a senha bloqueada, a senha **certa** também é recusada: `POST /login` → **423** (a tela mostra "Desbloqueie a sua senha"); a verificação do e-mail também responde **423** (desde 2026-10-15; antes, 427: a senha bloqueada agora é 423 em todo endpoint). Nenhuma resposta de login recusado traz `sessionToken`.
- [ ] 4.7 Senha nova + confirmação + token válido → **Salvar senha** → 200, login feito, ação original refeita.
- [ ] 4.8 Faça logout e entre com a senha nova: `POST /login` → **200** (medido: **14 s**), toast "Sucesso!!! O usuário '...' foi autenticado com sucesso!" e a ação original refeita.
  > Executado com um segundo e-mail de teste, porque o primeiro ficou com o token bloqueado (ver L7): **com o token bloqueado, nem a senha certa entra** — a verificação do e-mail responde 403 e a tela mostra só "Seu token está bloqueado!". Nesse estado o campo de e-mail também fica **somente leitura**; para usar outro e-mail é preciso fechar o modal e abri-lo de novo.

## L5 — Login concorrente (duas abas)

- [ ] 5.1 Com a aba 1 logada, abra **outra aba** (a sessão é por aba), faça o item 5 da preparação nela e abra o modal.
- [ ] 5.2 E-mail + senha certa → **Login** → `POST /login` → **409**. Esperado: tela **"Desbloqueie seu login"** com "Já há um login corrente em sua conta, pode ser que você não tenha feito a saída em seu último login, ou se trata de algum acesso concorrente em sua conta em outra estação de trabalho. De qualquer forma, preencha os campos deste formulário para desfazer o outro login corrente".
- [ ] 5.3 Senha + confirmação + token válido → **Salvar senha** → 200, login feito na aba 2.
- [ ] 5.4 Volte à aba 1 e faça uma ação que exige login (enviar uma sugestão). Esperado: a aba 1 perdeu o login (a API responde 401 e o modal de login abre). Se entrar de novo pela aba 1, recebe o 409 do 5.2, porque agora o login corrente é o da aba 2. *(Corrigido em 2026-10-11 — bug 3.)*
- [ ] 5.5 Logo depois do 5.3, faça login com o mesmo e-mail numa **terceira** aba. Esperado: 409 de novo, porque a sessão da aba 2 é o login corrente. Vale para qualquer sessão aberta por **"Salvar senha"** (primeiro acesso, troca de senha, desbloqueio). *(Corrigido em 2026-10-11 — bug 7.)*
- [ ] 5.6 Na aba 1 (sessão derrubada), clique em **Sair do Sistema**. Esperado: "O usuário '...' não está logado neste sistema!" (404), e a aba 2 **continua logada**.
- [ ] 5.7 Na aba 2, **Trocar Senha** (senha nova + token). Esperado: 200; qualquer outra sessão desse e-mail deixa de valer.

> **Regra das sessões (desde 2026-10-11):** cada e-mail tem **uma** sessão corrente. Login com senha e "Salvar senha" (primeiro acesso, troca, desbloqueio, "desfazer o outro login") abrem uma sessão nova, e todas as anteriores deixam de valer na hora, no jn e no vis. Uma sessão derrubada recebe 401 **sem contar tentativa** (uma aba antiga repetindo requisições não bloqueia a senha do dono).

## L6 — "Trocar o e-mail" e "Esqueceu sua senha?"

- [ ] 6.1 Na tela de senha, **Clique aqui para trocar o e-mail**. Esperado: volta à 1ª tela com o título "Trocar o e-mail" e o e-mail anterior já preenchido.
- [ ] 6.2 **Avançar** → tela de senha → **Esqueceu sua senha? Clique aqui!**. Esperado: "Refazer sua senha" com "Preencha os campos para refazer a sua senha" + a mensagem do token já enviado (como no 2.2).

## L7 — Bloqueio do token e desbloqueio pelo suporte

- [ ] 7.1 Na tela de senha nova (ex.: "Refazer sua senha"), preencha senha e confirmação e erre o token **3 vezes** (tokens diferentes). Esperado: as duas primeiras → "... você ainda pode tentar mais N vez(es)"; a terceira → `POST /password` → **429**, campos inativos e no rodapé, em vermelho, **"Seu token está bloqueado! Clique aqui para solicitar desbloqueio"**.
- [ ] 7.2 Clique em **solicitar desbloqueio** → `POST /token/request/unlocking` → **200**. Esperado: "A solicitação de desbloqueio do token para o e-mail '...' foi efetuada com sucesso, por favor, verifique a caixa de entrada, spam / lixo eletrônico deste e-mail para localizar o token que enviamos. Caso não o encontre, ..."
  > Observação: o texto fala em "token que enviamos", mas neste momento o suporte ainda não fez nada.
- [ ] 7.3 Clique de novo → **409**: "A solicitação de desbloqueio do token para o e-mail '...' já foi feita na data DD/MM/AAAA - HH:MM, se necessário, poderá ser refeita na data (dia seguinte)".
- [ ] 7.4 **Operador:** no arquivo `C:\logs\telegram\support-751717896.txt` chegou `/solveLoginTokenTicket unlockToken roteiro.login@teste.com`. Envie esse comando ao bot de suporte. Esperado (resposta do bot): "Ao endereço roteiro.login@teste.com, envie a seguinte mensagem: Você solicitou o desbloqueio de seu token ... O token que você deve informar no campo de token é XXXXXXXX".
  > Observação: o sistema **também** manda esse token novo por e-mail sozinho (o arquivo do e-mail é reescrito com ele); a instrução ao operador para mandar à mão é redundante.
- [ ] 7.5 Candidato: clique em **solicitar desbloqueio** de novo. Esperado: "O token informado não está bloqueado" e os campos voltam a funcionar. *(Corrigido em 2026-10-08 — antes os campos voltavam, mas "Salvar senha" reaplicava o bloqueio guardado no navegador sem consultar o servidor, e o candidato ficava preso.)*
- [ ] 7.6 Senha, confirmação e **o token novo** → **Salvar senha** → 200, login feito.
- [ ] 7.7 Conferir: as tentativas de token desse e-mail foram zeradas pelo desbloqueio (`jn_login_token_attempts`). *(Corrigido em 2026-10-08 — antes os 3 erros continuavam contando e o primeiro erro depois do desbloqueio já bloqueava de novo.)*
  > Regra do sistema: **um desbloqueio por dia** (confirmado em 2026-10-11: depois do desbloqueio, 3 tokens errados bloqueiam de novo, e o novo pedido responde 429). Um segundo pedido no mesmo dia responde 429 "A solicitação de desbloqueio do token ... já foi resolvida na data ..., ... envie-nos um e-mail ao endereço onias85@gmail.com ou se preferir, aguarde até a data ... para refazer a sua solicitação".

## L8 — Reenvio do token pelo suporte

- [ ] 8.1 Logado: **Trocar Senha** → "Não recebeu ou perdeu o token? **Clique aqui para reenviar**" → `POST /token/request/resending` → **200**: "A solicitação de reenvio do token para o e-mail '...' foi efetuada com sucesso, por favor, verifique a caixa de entrada, spam / lixo eletrônico deste e-mail para localizar o token que enviamos."
- [ ] 8.2 Clique de novo → **409**: "A solicitação de reenvio do token ... já foi feita na data ..., se necessário, poderá ser refeita na data ...".
- [ ] 8.3 **Operador:** `/solveLoginTokenTicket resendToken roteiro.login@teste.com` → o bot responde "Ao endereço ..., envie a seguinte mensagem: Você solicitou o reenvio de seu token ... o token que você deve informar no campo de token é XXXXXXXX" (e o e-mail sai sozinho com esse token).
- [ ] 8.4 Candidato clica em reenviar de novo → **429**: "A solicitação de reenvio do token ... já foi resolvida na data ..., por favor, verifique a caixa de entrada ... Caso a mensagem não tenha chegado, envie-nos um e-mail ao endereço onias85@gmail.com ou se preferir, aguarde até a data ... para refazer a sua solicitação de reenvio do token, que reenviaremos o token a este e-mail."
- [ ] 8.5 O token **anterior** deixou de valer: usá-lo conta como token errado.

## L9 — Dois candidatos intercalados no navegador

Use duas abas da mesma janela. A sessão fica no `sessionStorage`, que é de cada aba, e o cache de respostas do login fica no `localStorage`, que as duas abas compartilham, guardado **por e-mail**. Chame de D o candidato da aba 1 e de E o da aba 2, ambos com e-mails novos. Limpe o `localStorage` só antes de começar, na aba 1.

- [ ] 9.1 Aba 1: abra o modal e leve D até "Criando uma nova senha". Leia o token de D **na hora**.
- [ ] 9.2 Aba 2: abra o modal e leve E até "Criando uma nova senha". Leia o token de E (o arquivo do e-mail agora é o de E).
- [ ] 9.3 D: token errado → "você ainda pode tentar mais 2 vez(es)".
- [ ] 9.4 E: token errado → também "mais 2 vez(es)" (o erro de D não conta para E).
- [ ] 9.5 D: o mesmo token errado de novo → "Este token já foi digitado antes e está incorreto, tente outro!" (sem ir ao servidor). Outro token errado → "mais 1 vez(es)".
- [ ] 9.6 E: token certo → modal fecha, "Sucesso!!! ... autenticado" e "Sugestão enviada" **só na aba 2**.
- [ ] 9.7 D: 3º token errado → "Seu token está bloqueado! Clique aqui para solicitar desbloqueio". A aba 2 continua logada.
- [ ] 9.8 D: solicitar desbloqueio (200), de novo (409), operador resolve, solicitar de novo → "O token informado não está bloqueado", salvar com o token novo → login feito.
- [ ] 9.9 Saia do sistema nas duas abas e abra o modal de login de novo em cada uma.
- [ ] 9.10 D erra a senha (2 restantes), E erra (2 restantes: o erro de D não conta), D repete a mesma senha ("Esta senha já foi digitada antes...") e erra outra (1 restante), E acerta (login feito na aba 2), D erra a 3ª → "Desbloqueie a sua senha".
- [ ] 9.11 D: senha nova + token → login feito e ação refeita.

*Executado em 2026-10-11 de 9.1 a 9.11: tudo como esperado. O `localStorage` ficou com uma entrada por e-mail (D com as respostas 403/429 do bloqueio, E com 200), sem uma afetar a outra.*

---

## L10 — Sessão de outro navegador e virada da hora (desde 2026-10-15)

Feito pela automação (`automacao/03-modal-de-login.mjs`) ou com `curl`, porque a tela não troca de User-Agent.

- [ ] 10.1 Faça login com um e-mail novo e guarde o `sessionToken`. Com ele, chame `GET /login/{email}/{sessionToken}` quatro vezes com o cabeçalho `User-Agent: outro-navegador`. Esperado: **401** nas quatro, e `jn_password_attempts` desse e-mail sem tentativas (o token roubado não bloqueia a senha do dono).
- [ ] 10.2 A mesma chamada com o User-Agent do login. Esperado: **200**.
- [ ] 10.3 Login de novo pelo navegador original. Esperado: **409** "Desbloqueie seu login" (a sessão corrente continua válida), e não 423.
- [ ] 10.4 Errar a senha 3 vezes (429) e chamar `POST /login/{email}/token` (verificação do e-mail). Esperado: **423** `lockedPassword` (até 2026-10-14, 427).
- [ ] 10.5 Nenhuma resposta recusada de `POST /login` traz `sessionToken` (veja o corpo no Network).
- [ ] 10.6 Virada da hora: faça login alguns minutos antes da hora cheia e repita uma ação logada logo depois dela. Esperado: **200**. Até 2026-10-13 a sessão caía na virada da hora (401) e as repetições da tela bloqueavam a senha.

---

## Bugs encontrados na execução de 2026-10-08 (e na de 2026-10-11)

| # | O que acontecia | Situação |
|---|---|---|
| 1 | "Salvar senha" habilitado com os campos vazios; o clique ia ao servidor, voltava 422 e a tela não dizia nada | **Corrigido** (front): campos vazios mostram mensagem e não vão ao servidor; o botão começa desabilitado |
| 1b | O mesmo no "Login" com a senha vazia | **Corrigido** (front), igual ao 1 |
| 2 | "Token já enviado" (429) não era tratado: a tela esperava 409 e ficava calada em Trocar Senha, Esqueceu a senha, Desbloqueie a sua senha e Desbloqueie seu login | **Corrigido** (front): mostra quando o token foi enviado e quando expira |
| 3 | "Desfazer o outro login corrente" não derruba a sessão antiga, e nenhuma troca de senha derruba as anteriores: o e-mail de teste chegou a ter **3 sessões válidas** ao mesmo tempo. Confirmado de novo em 2026-10-11 pela automação: a sessão "desfeita" continua respondendo 200 em `GET /login/{email}/{sessionToken}` | **Corrigido em 2026-10-11** (decisão: derrubar a sessão antiga e todas as sessões na troca de senha). `jn_login_session_conflict` guarda o hash do token da sessão corrente (`currentSessionTokenHash`), e a validação da sessão (`JnBusinessCheckCurrentSession`, usada pelo jn e pelo vis) só aceita essa sessão. Sessão derrubada: 401 sem contar tentativa; logout por ela: 404 sem derrubar a corrente |
| 4 | O contador de tokens errados não zerava ao acertar o token nem quando o suporte desbloqueava; depois disso um único erro bloqueava de novo | **Corrigido** (backend: `JnBusinessSavePassword` e `JnBusinessResetLoginToken`) |
| 5 | Depois de o suporte desbloquear, "Salvar senha" reaplicava o bloqueio guardado no navegador sem consultar o servidor | **Corrigido** (front): a resposta "não está bloqueado" limpa o bloqueio guardado |
| 6 | O cache do navegador mistura as respostas "já resolvida" do desbloqueio e do reenvio (mesmo nome de status): um desbloqueio pedido depois de um reenvio resolvido respondeu, sem ir ao servidor, que o desbloqueio "já foi resolvido" (com a hora do reenvio) | Observado; a correção do 5 apaga esse cache na hora, e o clique seguinte vai ao servidor. Não corrigido na raiz |
| 7 | (2026-10-11) Sessão aberta por **"Salvar senha"** não conta como login corrente: um segundo login com o mesmo e-mail entra (200) em vez de receber 409 "Desbloqueie seu login". Causa: `JnBusinessSavePassword` roda, no mesmo bulk, `JnBulkHandlerRegisterLogin` (que cria o registro em `jn_login_session_conflict`) e depois `JnBulkHandlerSolveLoginConflict` (que apaga esse mesmo registro), então a sessão nova fica sem o registro de conflito. Só o login pelo botão **Login** grava o conflito | **Corrigido em 2026-10-11** (decisão: manter o padrão do botão Login): o `JnBulkHandlerSolveLoginConflict` saiu do bulk; o registro é criado ou, se já existe, atualizado com a sessão nova |

### Observações (não são erro de quem testa, mas merecem avaliação)
- Login, gravação de senha e verificação de e-mail levavam de 5 a 10 segundos (corrigido em 2026-10-09; ver o início do roteiro).
- O token vale um mês e pode ser reutilizado nesse prazo.
- O toast de troca de senha diz "autenticado".
- Pedido de desbloqueio aceito diz "localizar o token que enviamos" antes de o suporte agir.
- O bot pede ao operador para mandar o token à mão, mas o sistema já manda por e-mail.
- Um desbloqueio por dia: se o token bloquear de novo no mesmo dia, o candidato só consegue por e-mail ao suporte — e, com o token bloqueado, **nem a senha certa entra**.
- Com o token bloqueado o campo de e-mail fica somente leitura (não dá para trocar de e-mail sem fechar o modal).
- "Sair do Sistema" respondeu 404 ("O usuário '...' não está logado neste sistema!") para uma sessão que continuava sendo aceita pela API do vis — mais um sintoma do bug 3, corrigido em 2026-10-11 (hoje a sessão que responde 404 no logout também é recusada pelo vis).
