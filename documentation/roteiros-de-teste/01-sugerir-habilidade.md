# Roteiro 01 — Sugerir habilidade ("Deixamos de listar alguma habilidade?")

**Pré-requisito:** [00-preparacao-do-ambiente.md](00-preparacao-do-ambiente.md) feito até o item 5 (tela na aba Habilidades).

> **Executado de verdade em 2026-10-08**, no navegador (conta `roteiro.login2@teste.com`) e com o bot de suporte, de S1 a S7. Tudo bateu com o descrito abaixo; o que a execução revelou está nas notas **"Visto na execução"** e na seção [Observações da execução](#observações-da-execução-2026-10-08) no fim.
>
> **Executado de novo em 2026-10-10**, de S1 a S8 (S8 com a conta `roteiro.s8@teste.com`). Tudo bateu, exceto uma sugestão perdida quando o Telegram caiu, já corrigida. Os passos 1.18, 3.4 e 5.8b foram atualizados. Veja [Observações da execução (2026-10-10)](#observações-da-execução-2026-10-10).

## Como a funcionalidade funciona (resumo)

1. O candidato sugere uma habilidade que **consta no texto do currículo** e não foi listada, com sinônimos (várias frases) e uma justificativa.
2. A tela recusa sozinha o que já aparece no currículo, sem chamar o servidor. O servidor recusa:
   - o que o sistema já conhece, como habilidade **ou como sinônimo** (412);
   - o que esse candidato já teve rejeitado (410 — a rejeição é definitiva);
   - o que o operador já avaliou a partir da sugestão de **outro** candidato (410 `alreadyReviewed`): a decisão vale para todos, o candidato vê o status e o motivo do operador, e nenhum ticket novo é aberto;
   - o que já está pendente (409).
3. A sugestão fica **pendente** (`vis_skill_pending`): o candidato recebe um e-mail e o operador recebe no Telegram `/reviewSkillSuggestion <email> <habilidade>`.
4. Enquanto pendente, o modal é **só leitura**. Para alterar a sugestão, o candidato desiste dela e envia de novo.
5. O operador **aprova** ou **rejeita** (sempre com justificativa de 10 a 500 caracteres) ou **ignora** o candidato. O "ignorar" vale para **todos os comandos** do suporte, não só para este.
6. Se aprovada, vai para `vis_skill_approved`, entra em `vis_skill` e na tabela de leitura do currículo, com os sinônimos, e passa a ser reconhecida nos currículos. Se rejeitada, vai para `vis_skill_rejected`. Nos dois casos o candidato recebe um e-mail com a justificativa do operador.
7. Uma sugestão por candidato e habilidade (chave: e-mail + habilidade).

## Palavras usadas neste roteiro (todas do `cv.txt`)

Conferidas contra o currículo e a base de habilidades em 2026-10-08:

| Palavra | A tela deixa enviar? | O servidor conhece? | Usada no cenário |
|---|---|---|---|
| `PICK BY LIGHT` | sim | não | S1 (aprovar) |
| `KIPREV` | sim | não | S2 (rejeitar) |
| `BOLETOS` | sim | não | S3 (validações) e S4 (desistir) |
| `AMGSTROM` | sim | não | S5 (ignorar) |
| `JAB` | sim | não | S5 e S6 (pendingTickets) |
| `JAVA`, `WEM`, `ASP`, `PRIMEFACE`, `JVM` | **não** | — | S7 (bloqueios da tela) |

---

## S1 — Sugestão aprovada (o caminho completo)

### Candidato

- [ ] 1.1 Clique em **"Deixamos de listar alguma habilidade?"**. Abre o modal "Descreva a habilidade técnica que CONSTA no texto do seu currículo e que deixamos de listar aqui" com três campos e o botão **Enviar**.
- [ ] 1.2 Campo da habilidade: digite `pick  by light` (com dois espaços). Esperado: o texto já aparece em MAIÚSCULAS.
- [ ] 1.3 Clique no campo de sinônimos. Esperado: o campo da habilidade vira `PICK BY LIGHT` (um espaço só). Nenhum status aparece (ainda não há sugestão).
- [ ] 1.4 Sinônimos: digite `pick to light` e tecle **Enter** → vira uma etiqueta `PICK TO LIGHT`. Digite `ptl, put to light` e tecle **Enter** → viram duas etiquetas (`PTL`, `PUT TO LIGHT`). O campo ocupa a largura toda do modal.
- [ ] 1.5 Justificativa: `Consta no projeto da Volkswagen (2012): sistema de automacao Pick By Light na linha de montagem.`
- [ ] 1.6 **Enviar**. (Se for o primeiro envio desde o login, faça o login do item 4 da preparação; o envio é refeito sozinho.)

Esperado na tela:
- [ ] Mensagem verde **"Sugestão enviada — Obrigado! Sua sugestão será analisada e você será avisado do resultado."**
- [ ] O modal fecha.
- [ ] Network: `POST /resume/onias85@gmail.com/skills/suggestion` → **200**.

Esperado fora da tela:
- [ ] E-mail `...$VisNotifySupportAndUserAboutPendingSkillRequest.html`: "Olá, você sugeriu a habilidade PICK BY LIGHT (sinônimos: PICK TO LIGHT, PTL, PUT TO LIGHT). Nosso time está avaliando e te responderá o quanto antes."
- [ ] Telegram: o bot manda `/reviewSkillSuggestion onias85@gmail.com PICK BY LIGHT`.
- [ ] `vis_skill_pending`: um registro com `skill: PICK BY LIGHT`, os 3 sinônimos, a justificativa e o `email` em hash.
- [ ] `jn_versionable?q=entity:vis_skill_pending`: ganha um registro de histórico (o índice é cumulativo — conte antes e depois).
- [ ] `jn_support_pending_command`: `"command": "/reviewSkillSuggestion onias85@gmail.com PICK BY LIGHT"`.

### Candidato consulta a sugestão pendente

- [ ] 1.7 Abra o modal de novo. Esperado: campos vazios e habilitados, botão **Enviar**.
- [ ] 1.8 Digite `Pick by light` e clique fora do campo. Esperado:
  - os sinônimos e a justificativa são carregados;
  - **os três campos ficam desabilitados**;
  - aparece **"status: Pendente"** e o aviso "Esta sugestão está em análise. Para alterá-la, desista dela e envie uma nova.";
  - os botões são **"Desistir da sugestão"** e **"Nova sugestão"** (não há mais "Enviar").
- [ ] 1.9 Clique em **Nova sugestão**. Esperado: os campos se esvaziam e voltam a ficar habilitados, com o botão **Enviar**. Feche o modal.

> **409 (opcional, só por fora da tela):** a tela não deixa reenviar uma sugestão pendente. O servidor responde **409** se alguém enviar `PICK BY LIGHT` de novo para o mesmo e-mail (outra aba aberta antes do primeiro envio, Postman). Na tela, o aviso é "Sugestão já pendente — Você já sugeriu a habilidade 'PICK BY LIGHT' e ela ainda está em análise."

### Operador

- [ ] 1.10 No Telegram, copie a mensagem `/reviewSkillSuggestion onias85@gmail.com PICK BY LIGHT` e envie ao bot. Esperado:

```
Sugestão de habilidade de onias85@gmail.com

Habilidade: PICK BY LIGHT
Sinônimos: PICK TO LIGHT, PTL, PUT TO LIGHT
Justificativa do usuário: Consta no projeto da Volkswagen (2012): ...

Responda com uma das opções:
• aprovar <justificativa> — aprova a habilidade, que passa a ser reconhecida nos currículos
• rejeitar <justificativa> — rejeita a habilidade
• ignorar — descarta a sugestão e ignora as próximas deste usuário em todos os comandos
A justificativa vai para o usuário e precisa ter de 10 a 500 caracteres.
```

- [ ] 1.11 Responda `aprovar ok`. Esperado: "Não entendi a resposta. Toda decisão precisa vir acompanhada de uma justificativa de 10 a 500 caracteres." seguido das opções (justificativa curta demais).
- [ ] 1.12 Responda `um a um`. Esperado: a mesma mensagem de "Não entendi" (essa opção só existe no ajuste de hierarquia).
- [ ] 1.13 Responda `aprovar ferramenta de automação industrial relevante`. Esperado: "A habilidade PICK BY LIGHT sugerida por onias85@gmail.com foi aprovada. O usuário será avisado por e-mail."

Esperado depois da aprovação:
- [ ] `vis_skill_pending`: o registro sumiu.
- [ ] `vis_skill_approved`: o registro está lá, com `explanation` = a sua justificativa.
- [ ] `vis_skill?q=skill:"PICK BY LIGHT"`: a habilidade existe, com os sinônimos e um `ranking` (o último + 1).
- [ ] E-mail `...$VisNotifyUserAboutAprovedSkill.html`: "Olá, a habilidade PICK BY LIGHT que você sugeriu foi aprovada pelo nosso time e passa a ser reconhecida nos currículos." e a sua justificativa.
- [ ] Tickets: `/reviewSkillSuggestion ... PICK BY LIGHT` não está mais em `jn_support_pending_command` nem em `jb_pending_tickets`.
- [ ] 1.14 Envie o mesmo comando de novo ao bot. Esperado: "Não há sugestão pendente da habilidade 'PICK BY LIGHT' para o e-mail 'onias85@gmail.com'".

### Candidato vê o resultado

- [ ] 1.15 Abra o modal, digite `PICK BY LIGHT` e clique fora. Esperado: **"status: Aprovada"**, um painel **"Motivo"** com a justificativa do operador, os campos desabilitados, o botão **"Nova sugestão"** e nenhum "Desistir".
- [ ] 1.16 Clique em **Nova sugestão**: os campos se esvaziam. Feche o modal.
- [ ] 1.17 **Reprocesse o currículo** (espaço no fim do texto + **Idiomas**) e volte à aba Habilidades. Esperado: `PICK BY LIGHT` aparece agora na lista "Habilidades pelas quais eu quero que o meu currículo seja ENCONTRADO" (o contador passa de 105 para 106), sem nenhum conhecimento implícito associado.
  > **Visto na execução:** confirmado (105 → 106), mas na época só depois de reiniciar a API do vis. A aprovação limpa o cache no mesmo instante, porém roda em outro processo (o leitor do bot), e localmente cada processo tinha o seu cache em memória. **Corrigido em 2026-10-08:** localmente, a limpeza feita por um processo vale para todos, como já acontece em produção com o Memcache compartilhado. Não é mais preciso reiniciar nada.
- [ ] 1.18 Tente sugerir `PTL` (sinônimo recém-aprovado). Esperado: a tela barra sozinha, com o aviso amarelo **"Habilidade fora do currículo — A habilidade 'PTL' não aparece no texto do seu currículo. Só é possível sugerir uma habilidade escrita exatamente como consta nele."** Nada vai ao servidor.
  > **412 (opcional, só por fora da tela):** se alguém enviar `PTL` direto ao servidor (Postman), ele recusa com **412** "Habilidade já reconhecida", porque PTL já é sinônimo conhecido.
  >
  > **Mudou em 2026-10-08:** antes a tela não barrava `PTL` e quem recusava era o servidor. Desde que a tela só aceita frases que constam no currículo, o 412 não aparece mais por ela.

---

## S2 — Sugestão rejeitada (a rejeição é definitiva)

### Candidato
- [ ] 2.1 Sugira `KIPREV`, sinônimo `KI PREV`, justificativa `Projeto do Santander citado no currículo, de exposição de PL/SQL em REST.` → **Enviar** → "Sugestão enviada".

### Operador
- [ ] 2.2 Envie ao bot o comando que chegou (`/reviewSkillSuggestion onias85@gmail.com KIPREV`).
- [ ] 2.3 Responda `rejeitar é o nome de um <projeto>, não uma habilidade técnica`. Esperado: "A habilidade KIPREV sugerida por onias85@gmail.com foi rejeitada. O usuário será avisado por e-mail."

### Conferir
- [ ] 2.4 `vis_skill_rejected`: registro com `explanation`. `vis_skill`: **não** tem KIPREV.
- [ ] 2.5 E-mail `...$VisNotifyUserAboutRejectedSkill.html`: "Olá, a habilidade KIPREV que você sugeriu não foi aprovada pelo nosso time." e a justificativa com `<projeto>` aparecendo como texto (o HTML é escapado).
- [ ] 2.6 Na tela, digite `KIPREV` no modal e clique fora. Esperado: **"status: Rejeitada"** + **Motivo**, campos desabilitados, botão **Nova sugestão**.
- [ ] 2.7 Clique em **Nova sugestão**, digite `KIPREV` de novo e clique fora. Esperado: volta a mostrar "Rejeitada" com o motivo. **Não há como reenviar uma habilidade rejeitada** — é a regra.

> **410 (opcional, só por fora da tela):** se alguém enviar `KIPREV` de novo para o mesmo e-mail (Postman), o servidor responde **410** e nada fica pendente. Na tela, o aviso seria "Sugestão já avaliada — A habilidade 'KIPREV' já foi sugerida por você e rejeitada pelo suporte."

---

## S3 — Validações da tela (nenhuma chega ao servidor)

Para cada linha, abra o modal, preencha e clique em **Enviar**. Esperado: aviso amarelo, o modal continua aberto e nada aparece no Network.

| # | Habilidade | Sinônimos | Justificativa | Aviso esperado |
|---|---|---|---|---|
| - [ ] 3.1 | `X` | — | `Justificativa com mais de dez letras` | "Habilidade inválida — 'X' deve ter entre 2 e 50 caracteres." |
| - [ ] 3.2 | `BOLETOS` | `G` | `Justificativa com mais de dez letras` | "Sinônimo inválido — 'G' deve ter entre 2 e 50 caracteres." |
| - [ ] 3.3 | `BOLETOS` | — | `curta` | "Explicação inválida — A explicação deve ter entre 10 e 500 caracteres." |
| - [ ] 3.4 | `BOLETOS` | `BOLETOS` | `Justificativa com mais de dez letras` | **envia** (o sinônimo igual à própria habilidade é descartado antes do envio). Depois, desista dela (como no S4.2 a 4.4) para o S4 começar sem ela. |

> **Mudou em 2026-10-10:** até então este cenário usava `GEORREFERENCIAMENTO`, que não consta no `cv.txt`. Desde 2026-10-08 a tela recusa frases fora do currículo ("Habilidade fora do currículo"), e o 3.4 deixou de enviar. Os avisos de 3.1 a 3.3 aparecem antes dessa checagem, por isso não mudavam.

---

## S4 — Candidato desiste da sugestão

- [ ] 4.1 Sugira `BOLETOS`, justificativa `Processamento de boletos no cliente Sicoob, citado no currículo.` → Enviar.
- [ ] 4.2 Abra o modal, digite `BOLETOS`, clique fora → "status: Pendente", campos desabilitados, botões "Desistir da sugestão" e "Nova sugestão".
- [ ] 4.3 **Desistir da sugestão** → confirmação "Tem certeza de que deseja desistir desta sugestão? Ela deixará de ser analisada." → **Não**: nada acontece.
- [ ] 4.4 **Desistir da sugestão** → **Sim, desistir**. Esperado: "Sugestão retirada — Sua sugestão não será mais analisada.", o modal fecha, Network `DELETE ...skills/suggestion` → 200, `vis_skill_pending` sem BOLETOS.
- [ ] 4.5 Operador: envie ao bot o comando que tinha chegado (`/reviewSkillSuggestion onias85@gmail.com BOLETOS`). Esperado: "Não há sugestão pendente da habilidade 'BOLETOS' ...". O ticket some de `/pendingTickets`.
  > **Corrigido em 2026-10-08:** na execução, desistir pela tela não tirava o ticket de `/pendingTickets`. Agora a desistência cancela o ticket: no próximo `/pendingTickets` ele já não aparece (vale também para o ajuste de hierarquia).
- [ ] 4.6 Sugira `BOLETOS` de novo (agora com outra justificativa). Esperado: aceita — desistir não é rejeição.

**Variante — desistir durante a revisão:**
- [ ] 4.7 Com `BOLETOS` pendente, o operador envia o comando e recebe a sugestão (não responda ainda).
- [ ] 4.8 O candidato desiste pela tela (4.2 a 4.4).
- [ ] 4.9 O operador responde `aprovar habilidade relevante para o mercado`. Esperado: "A sugestão da habilidade 'BOLETOS' do e-mail 'onias85@gmail.com' não está mais pendente: o usuário desistiu dela." Nada é aprovado.

**Variante — desistir de algo que acabou de ser avaliado:**
- [ ] 4.10 Sugira algo, abra o modal (status Pendente), deixe aberto; o operador aprova ou rejeita; clique em **Desistir** → **Sim**. Esperado: "Sugestão não encontrada — Não encontramos uma sugestão pendente para desistir. Ela pode já ter sido analisada." e o modal recarrega o status real.

---

## S5 — Operador ignora o candidato (vale para todos os comandos)

> Este cenário bloqueia o seu próprio e-mail **em todos os comandos** do suporte. O passo 5.9 desfaz isso — não pule.

- [ ] 5.1 Candidato sugere `AMGSTROM`, justificativa `Linux embarcado usado no projeto Pick By Light da Volkswagen.` Deixe também pendentes `BOLETOS` (S4.1) e um ajuste de hierarquia qualquer (roteiro 02), para ver que **tudo** some no 5.6.
- [ ] 5.2 Operador envia `/reviewSkillSuggestion onias85@gmail.com AMGSTROM`.
- [ ] 5.3 Responde `ignorar`. Esperado: "Confirma que o usuário onias85@gmail.com será ignorado pelo suporte, em todos os comandos? Esta sugestão será descartada sem aviso ao usuário e as próximas não chegarão mais a você. Responda: sim ou não"
- [ ] 5.4 Responde `talvez`. Esperado: "Não entendi a resposta." + a mesma pergunta.
- [ ] 5.5 Responde `não`. Esperado: "O usuário não será ignorado." + as opções. Responde `ignorar` de novo e depois `sim`. Esperado: "O usuário onias85@gmail.com foi ignorado pelo suporte, em todos os comandos. A sugestão da habilidade AMGSTROM foi descartada."
- [ ] 5.6 Conferir: **todas** as pendências do candidato somem como se nunca tivessem existido (desde 2026-10-10): `vis_skill_pending` sem AMGSTROM nem BOLETOS, `vis_skill_fix_hierarchy_pending` sem o ajuste dele, nenhum histórico delas em `jn_versionable`, e os tickets delas fora do `/pendingTickets`. Itens de hierarquia que outro candidato também pediu continuam pendentes. Também: `vis_command_not_allowed_to_user` com **um** registro do e-mail (em hash), `commandName: reviewSkillSuggestion` (só registra onde a decisão foi tomada) e a sugestão na `description`; **nenhum** e-mail de rejeição gerado.
- [ ] 5.7 Candidato sugere `JAB`, justificativa `Java Arquitetura Brasil, framework do Santander.` Esperado: aviso vermelho **"Falha ao enviar sugestão"**; Network **403**; nada pendente; nada chega ao Telegram.
- [ ] 5.8 **Ignorar é global:** o candidato tenta um ajuste de hierarquia (⊕ de qualquer conhecimento implícito, uma habilidade, justificativa válida). Esperado: também **403** / "Falha ao enviar sugestão".
- [ ] 5.8b Se o operador digitar `/reviewSkillSuggestion onias85@gmail.com JAB` (ou qualquer `/fixSkillHierarchy ... onias85@gmail.com ...`), o bot responde: "O usuário onias85@gmail.com está sendo ignorado pelo suporte e as solicitações dele não são atendidas em nenhum comando. Para voltar a atendê-lo, use /permitirComandoAoUsuario onias85@gmail.com"
  > O bot indica o comando pelo nome no idioma do operador (português aqui, desde 2026-10-10). O nome canônico `/allowCommandToUser` continua valendo.
- [ ] 5.9 Operador envia `/permitirComandoAoUsuario onias85@gmail.com` (ou `/allowCommandToUser onias85@gmail.com`). Esperado: "O usuário onias85@gmail.com não é mais ignorado pelo suporte: as próximas solicitações dele, em todos os comandos, voltarão a chegar ao suporte." O registro sai de `vis_command_not_allowed_to_user` e vai para `vis_command_reallowed_to_user`.
- [ ] 5.10 Envie o mesmo `/allowCommandToUser` de novo. Esperado: "O usuário onias85@gmail.com não está sendo ignorado pelo suporte"

---

## S6 — Pelo `/pendingTickets`

- [ ] 6.1 Candidato sugere `JAB` (depois do 5.9), justificativa `Java Arquitetura Brasil, framework do Santander.`
- [ ] 6.2 Operador envia `/pendingTickets`. Esperado: "Você tem N tickets para resolver" e "Ticket 1 de N => /reviewSkillSuggestion onias85@gmail.com JAB — Digite "1" para resolver ou "2" para ir ao próximo" (a ordem é do mais antigo para o mais novo; use `2` até chegar ao de JAB).
- [ ] 6.3 Responde `1`. Esperado: "Resolvendo o ticket ..." e logo a sugestão de JAB com as opções, como se você tivesse digitado o comando.
- [ ] 6.4 Rejeite com justificativa. Esperado: depois do resumo, a lista de tickets reabre sem o de JAB.

> **Teste com habilidade de várias palavras:** repita 6.1–6.4 com uma habilidade com espaços **que conste no currículo** e que o sistema ainda não conheça (desde 2026-10-08 a tela recusa frases fora do currículo, como `PICK TO LIGHT SYSTEM`, usada na execução). O caminho "1" do `/pendingTickets` com habilidade de várias palavras **não tem teste automático** — é o ponto mais importante a observar aqui.
>
> **Visto na execução:** funciona. `PICK TO LIGHT SYSTEM` (sinônimo `PTL SYSTEM`) chegou inteiro pelo "1", foi aprovado e entrou em `vis_skill` com o sinônimo.
>
> **Visto na execução:** se o operador responder `2` menos de 1 segundo depois do `/pendingTickets`, o total pode cair por um instante ("Ticket 2 de 20" logo depois de "Ticket 1 de 21"). É o atraso de refresh do Elasticsearch para os tickets recém-movidos. Uma pessoa digitando não chega a ver isso.

---

## S7 — O que a tela barra sozinha (nada vai ao servidor)

Sugira cada palavra (qualquer justificativa válida) e clique em **Enviar**. Esperado: aviso amarelo, o modal fica aberto, nada no Network.

| # | Sugestão | Aviso esperado | Por quê |
|---|---|---|---|
| - [ ] 7.1 | `JAVA` | "A palavra 'JAVA' já está relacionada em sua lista de ferramentas" | já está na sua lista |
| - [ ] 7.2 | `WEM` | "O sinônimo (VCM) para esta palavra já está presente em sua lista" | WEM é sinônimo de VCM |
| - [ ] 7.3 | `ASP` | "O nome desta ferramenta é parte de uma outra palavra "ASPECTJ" presente no texto do seu currículo" | só aparece dentro de ASPECTJ |
| - [ ] 7.4 | `PRIMEFACE` | "Esta ferramenta é um pedaço de outra ferramenta "PRIMEFACES" já adicionada à sua lista" | pedaço de PRIMEFACES |
| - [ ] 7.5 | `JVM` | "... já está relacionada em sua lista de ferramentas porém como pré requisito das palavras [...]" | é conhecimento implícito de várias da lista |
| - [ ] 7.6 | `PICK TO LIGHT SYSTEM` | "Habilidade fora do currículo — A habilidade 'PICK TO LIGHT SYSTEM' não aparece no texto do seu currículo. Só é possível sugerir uma habilidade escrita exatamente como consta nele." | a frase não consta no currículo |

> **Defesa do servidor (opcional, com Postman ou similar):** o servidor também recusa `JAVA`, `WEM`, `ASP` e `JVM` com **412** mesmo se a chamada não vier da tela — inclusive `WEM`, que é só sinônimo. `PRIMEFACE` passaria (não é palavra conhecida, só pedaço de uma): só a tela, que lê o currículo, sabe barrá-la.
>
> **Visto na execução:** JAVA, ASP e JVM → 412. Na sessão anterior, WEM e PRIMEFACE → 412 e KIPREV (rejeitada) → 410. O PRIMEFACE dá 412 porque, nesta base, ele já é palavra conhecida.

---

## S8 — Outro candidato sugere o que o operador já avaliou (sem ticket novo)

**Pré-requisito:** S1 (`PICK BY LIGHT` aprovada) e S2 (`KIPREV` rejeitada) feitos **depois de 2026-10-10**. Decisões anteriores a essa data não foram registradas por habilidade e não valem para os outros candidatos.

- [ ] 8.1 Saia e faça login com **outra conta**, cujo currículo também contenha `KIPREV`. Para sair, use no console `localStorage.removeItem('logins'); sessionStorage.removeItem('login')` e recarregue. Depois preencha a aba Currículo com o mesmo `cv.txt` (item 5 da preparação). O login da conta nova é pedido ao enviar `KIPREV` no 8.3.
- [ ] 8.2 Abra o modal, digite `KIPREV` e clique fora. Esperado: **"status: Rejeitada"** + **Motivo** com a justificativa que o operador deu no S2. Os campos ficam desabilitados e aparece o botão **Nova sugestão**. A justificativa do primeiro candidato **não** aparece (o campo fica vazio).
- [ ] 8.3 Só por fora da tela (Postman): enviar `KIPREV` para esta conta. Esperado: **410** (`alreadyReviewed`). Nada fica pendente em `vis_skill_pending`, e nada chega ao Telegram nem a `jn_support_pending_command` / `/pendingTickets`.
  Se o 410 chegar à tela (habilidade avaliada entre digitar e enviar), aparece o aviso "Sugestão já avaliada — A habilidade 'KIPREV' já foi avaliada pelo suporte. Veja abaixo o resultado e o motivo." e o modal mostra a decisão.
- [ ] 8.4 Digite `PICK BY LIGHT` (se a tela deixar: depois do reprocessamento ela já é reconhecida no currículo). Esperado: **"status: Aprovada"** + **Motivo**. Se o envio chegar ao servidor, vem o **412** "Habilidade já reconhecida", e o modal também mostra a decisão.
- [ ] 8.5 `vis_skill_reviewed`: um registro por habilidade (`KIPREV` → `rejected`, `PICK BY LIGHT` → `approved`), com `explanation` e sinônimos, sem e-mail.

---

## Observações da execução (2026-10-08)

| # | O que se viu | Gravidade |
|---|---|---|
| 1 | Desistir pela tela não dava baixa no ticket do operador (4.5). | **corrigido** |
| 2 | Uma aprovação só aparecia na lista do currículo depois de reiniciar a API do vis (1.17). | **corrigido** no ambiente local (cache compartilhado entre processos) |
| 3 | Sugestão sem sinônimo: o bot mostra a linha `Sinônimos:` vazia, sem "(nenhum)". | cosmético |
| 4 | Os avisos de WEM, ASP e PRIMEFACE repetem o título no corpo, com o mesmo texto duas vezes. | cosmético |
| 5 | Para palavra já conhecida, o 412 vem antes do 403 do usuário ignorado: o ignorado recebe "Habilidade já reconhecida", e não "Falha ao enviar". | informativo |
| 6 | O modal "CONSTA no texto do seu currículo" aceitava palavra que não está no currículo (`PICK TO LIGHT SYSTEM`). | **corrigido**: a tela só aceita uma frase que conste exatamente no currículo (aviso "Habilidade fora do currículo") |

## Observações da execução (2026-10-10)

| # | O que se viu | Gravidade |
|---|---|---|
| 1 | O aviso de `KIPREV` ao Telegram falhou por uma queda momentânea de conexão (`Connection reset`). O candidato viu "Sugestão enviada", recebeu o e-mail e a sugestão ficou pendente, mas o ticket do operador só era gravado depois de um envio bem-sucedido. Resultado: nada no Telegram e nada no `/pendingTickets`, e o operador nunca saberia da sugestão. | **corrigido**: o ticket é gravado antes da tentativa de envio. Se o Telegram falhar, a sugestão aparece no `/pendingTickets` |
| 2 | Na mesma falha, o aviso do erro ao suporte (um arquivo de 46 KB) foi registrado como falha de envio: depois que o Telegram já tinha aceitado o arquivo, o log do pedido em `toCurl` tentava ler o corpo multipart como texto e o Apache recusava acima de 25 KB (`ContentTooLongException`, em `jn_jobsnow_warning`). | **corrigido**: o `toCurl` só descreve o corpo multipart (tipo e tamanho) e nunca faz uma requisição falhar |
| 3 | Passos 1.18, 3.4 e 5.8b desatualizados: a tela agora barra frases fora do currículo, e o bot mostra os comandos em português. | **roteiro atualizado** |
| 4 | Sugestão sem sinônimo: o e-mail de "sugestão recebida" mostra `(sinônimos: )` vazio, como a linha `Sinônimos:` do bot (observação 3 de 2026-10-08). | cosmético |
| 5 | A confirmação do `ignorar` ainda diz "Esta sugestão será descartada", mas desde 2026-10-10 **todas** as pendências do candidato são descartadas. | cosmético |
| 6 | Para trocar de conta no navegador não basta apagar `logins` do localStorage: a sessão também fica em `sessionStorage` (`login`). | informativo (ver item 4 da preparação) |

---

## Resumo do que este roteiro cobre

| Regra | Cenário |
|---|---|
| Normalização (maiúsculas, espaços) e sinônimos em etiquetas | S1 |
| Consulta de status ao digitar a habilidade (Pendente / Aprovada / Rejeitada); modal só leitura com sugestão carregada | S1, S2, S4 |
| 409 já pendente; 410 já rejeitada; 412 já conhecida (inclusive sinônimo); 403 ignorado; 404 ao desistir do que não está pendente | S1, S2, S7, S5, S4 |
| E-mails: recebida, aprovada, rejeitada (com escape de HTML) | S1, S2 |
| Bot: justificativa obrigatória (10–500), aprovar, rejeitar, ignorar com confirmação, desfazer o ignorar | S1, S2, S5 |
| Ignorar vale para todos os comandos | S5 |
| Aprovada entra em `vis_skill` e passa a ser lida nos currículos | S1 |
| `/pendingTickets` entra e sai | S1, S4, S6 |
| Decisão do operador vale para todos os candidatos (410 `alreadyReviewed`, sem ticket novo) | S8 |
| Validações da tela e bloqueios locais | S3, S7 |
