# Roteiro 03 — Modal de login

**Pré-requisito:** [00-preparacao-do-ambiente.md](00-preparacao-do-ambiente.md) até o item 3 (ambiente no ar e, de preferência, índices recriados).

> **Este roteiro foi executado de verdade no navegador em 2026-10-08**: cada texto "Esperado" abaixo foi visto na tela, no Network ou nos arquivos. Os poucos passos que **não** foram executados estão marcados como tal. Os bugs encontrados no caminho estão no fim, com o que foi corrigido.

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
- **Lentidão:** login, gravação de senha e verificação de e-mail levam de **5 a 10 segundos** cada (medido). Espere o botão voltar antes de concluir que travou.

## Dados

- E-mail de teste: use um e-mail que **ainda não existe** (ex.: `roteiro.login@teste.com`). Não use o seu e-mail real: o roteiro bloqueia senha e token.
- Senhas: qualquer uma com 8+ caracteres, maiúscula, número e caractere especial (ex.: `Roteiro@2026`, `Roteiro@2027`...).
- Antes de começar: **F12 → Console** → `localStorage.removeItem('logins'); sessionStorage.removeItem('login')` (o navegador guarda respostas de login por e-mail e pode pular telas).

## Como abrir o modal

1. Faça o item 5 da preparação (tela do currículo → **Idiomas** → aba **Habilidades**). Atenção: o 1º clique em **Idiomas** só valida o formulário (se faltar função ou LinkedIn, aparece "Falha!!! Deve-se informar ..." no canto); quando tudo está preenchido, ele lê o currículo.
2. Clique em **"Deixamos de listar alguma habilidade?"**, digite qualquer habilidade (ex.: `HABILIDADE DE TESTE 1`) e uma justificativa com 10+ caracteres, e clique em **Enviar**.
3. Sem login, abre **"Diga quem é você, antes de continuar..."**. A cada vez que precisar abrir o modal de novo, use outra habilidade (`HABILIDADE DE TESTE 2`, ...).

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
- [ ] 4.6 `Errada@333` → `POST /login` → **429**. Esperado: tela **"Desbloqueie a sua senha"** com "Devido a tentativas de acessos suspeitos, sua senha foi preventivamente bloqueada. Preencha os campos acima, para desbloqueá-la." e a mensagem do token ainda válido (como no 2.2).
- [ ] 4.7 Senha nova + confirmação + token válido → **Salvar senha** → 200, login feito, ação original refeita.
- [ ] 4.8 Faça logout e entre com a senha nova: `POST /login` → **200** (medido: **14 s**), toast "Sucesso!!! O usuário '...' foi autenticado com sucesso!" e a ação original refeita.
  > Executado com um segundo e-mail de teste, porque o primeiro ficou com o token bloqueado (ver L7): **com o token bloqueado, nem a senha certa entra** — a verificação do e-mail responde 403 e a tela mostra só "Seu token está bloqueado!". Nesse estado o campo de e-mail também fica **somente leitura**; para usar outro e-mail é preciso fechar o modal e abri-lo de novo.

## L5 — Login concorrente (duas abas)

- [ ] 5.1 Com a aba 1 logada, abra **outra aba** (a sessão é por aba), faça o item 5 da preparação nela e abra o modal.
- [ ] 5.2 E-mail + senha certa → **Login** → `POST /login` → **409**. Esperado: tela **"Desbloqueie seu login"** com "Já há um login corrente em sua conta, pode ser que você não tenha feito a saída em seu último login, ou se trata de algum acesso concorrente em sua conta em outra estação de trabalho. De qualquer forma, preencha os campos deste formulário para desfazer o outro login corrente".
- [ ] 5.3 Senha + confirmação + token válido → **Salvar senha** → 200, login feito na aba 2.
- [ ] 5.4 Volte à aba 1 e faça uma ação que exige login (enviar uma sugestão). **Esperado pelo texto do 5.2:** a aba 1 perdeu o login. **Visto em 2026-10-08:** a aba 1 continua funcionando com a sessão antiga. → ver **⚠ Bug 3** no fim.

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
  > Regra do sistema: **um desbloqueio por dia**. Um segundo pedido no mesmo dia responde 429 "A solicitação de desbloqueio do token ... já foi resolvida na data ..., ... envie-nos um e-mail ao endereço onias85@gmail.com ou se preferir, aguarde até a data ... para refazer a sua solicitação".

## L8 — Reenvio do token pelo suporte

- [ ] 8.1 Logado: **Trocar Senha** → "Não recebeu ou perdeu o token? **Clique aqui para reenviar**" → `POST /token/request/resending` → **200**: "A solicitação de reenvio do token para o e-mail '...' foi efetuada com sucesso, por favor, verifique a caixa de entrada, spam / lixo eletrônico deste e-mail para localizar o token que enviamos."
- [ ] 8.2 Clique de novo → **409**: "A solicitação de reenvio do token ... já foi feita na data ..., se necessário, poderá ser refeita na data ...".
- [ ] 8.3 **Operador:** `/solveLoginTokenTicket resendToken roteiro.login@teste.com` → o bot responde "Ao endereço ..., envie a seguinte mensagem: Você solicitou o reenvio de seu token ... o token que você deve informar no campo de token é XXXXXXXX" (e o e-mail sai sozinho com esse token).
- [ ] 8.4 Candidato clica em reenviar de novo → **429**: "A solicitação de reenvio do token ... já foi resolvida na data ..., por favor, verifique a caixa de entrada ... Caso a mensagem não tenha chegado, envie-nos um e-mail ao endereço onias85@gmail.com ou se preferir, aguarde até a data ... para refazer a sua solicitação de reenvio do token, que reenviaremos o token a este e-mail."
- [ ] 8.5 O token **anterior** deixou de valer: usá-lo conta como token errado.

---

## Bugs encontrados na execução de 2026-10-08

| # | O que acontecia | Situação |
|---|---|---|
| 1 | "Salvar senha" habilitado com os campos vazios; o clique ia ao servidor, voltava 422 e a tela não dizia nada | **Corrigido** (front): campos vazios mostram mensagem e não vão ao servidor; o botão começa desabilitado |
| 1b | O mesmo no "Login" com a senha vazia | **Corrigido** (front), igual ao 1 |
| 2 | "Token já enviado" (429) não era tratado: a tela esperava 409 e ficava calada em Trocar Senha, Esqueceu a senha, Desbloqueie a sua senha e Desbloqueie seu login | **Corrigido** (front): mostra quando o token foi enviado e quando expira |
| 3 | "Desfazer o outro login corrente" não derruba a sessão antiga, e nenhuma troca de senha derruba as anteriores: o e-mail de teste chegou a ter **3 sessões válidas** ao mesmo tempo | **⚠ Aguardando decisão** |
| 4 | O contador de tokens errados não zerava ao acertar o token nem quando o suporte desbloqueava; depois disso um único erro bloqueava de novo | **Corrigido** (backend: `JnBusinessSavePassword` e `JnBusinessResetLoginToken`) |
| 5 | Depois de o suporte desbloquear, "Salvar senha" reaplicava o bloqueio guardado no navegador sem consultar o servidor | **Corrigido** (front): a resposta "não está bloqueado" limpa o bloqueio guardado |
| 6 | O cache do navegador mistura as respostas "já resolvida" do desbloqueio e do reenvio (mesmo nome de status): um desbloqueio pedido depois de um reenvio resolvido respondeu, sem ir ao servidor, que o desbloqueio "já foi resolvido" (com a hora do reenvio) | Observado; a correção do 5 apaga esse cache na hora, e o clique seguinte vai ao servidor. Não corrigido na raiz |

### Observações (não são erro de quem testa, mas merecem avaliação)
- Login, gravação de senha e verificação de e-mail levam de 5 a 10 segundos.
- O token vale um mês e pode ser reutilizado nesse prazo.
- O toast de troca de senha diz "autenticado".
- Pedido de desbloqueio aceito diz "localizar o token que enviamos" antes de o suporte agir.
- O bot pede ao operador para mandar o token à mão, mas o sistema já manda por e-mail.
- Um desbloqueio por dia: se o token bloquear de novo no mesmo dia, o candidato só consegue por e-mail ao suporte — e, com o token bloqueado, **nem a senha certa entra**.
- Com o token bloqueado o campo de e-mail fica somente leitura (não dá para trocar de e-mail sem fechar o modal).
- "Sair do Sistema" respondeu 404 ("O usuário '...' não está logado neste sistema!") para uma sessão que continuava sendo aceita pela API do vis — mais um sintoma do bug 3 (o controle de sessões está inconsistente).
