# Decisões pendentes da execução do roteiro 05 (2026-10-15)

Achados da execução do [roteiro 05](../../05-endpoints-do-curriculo-pela-tela.md) e uma questão das siglas das regras de arquitetura. Cada um contado do ponto de vista do candidato, com as opções e a recomendação.

## Resumo

| # | Origem | Caso de uso | Situação atual | Rec. |
|---|---|---|---|---|
| 1 | R05-1 | Exclui numa janela e inativa em outra | Abas mantêm os dados apagados | a |
| 2 | R05-2 | Abre a tela do currículo | `GET` devolve a lista `hash` | a |
| 3 | R05-3 | Faz login após a sessão acabar | Modal usa um 409 antigo | a |
| 4 | R05-4 | Inativa ou reativa o currículo | Dois `exists` (regra FSED) | a |
| 5 | Siglas | Cita uma regra pela sigla | Seis siglas de duas letras | b |

| # | Opção a | Opção b | Opção c |
|---|---|---|---|
| 1 | limpar as abas e avisar | só avisar | manter |
| 2 | só os campos da tela | manter | — |
| 3 | sempre perguntar ao servidor | validade curta | manter |
| 4 | corrigir agora | depois | — |
| 5 | três letras | manter | — |

## Decisões tomadas (2026-10-15)

| # | Decisão | O que foi feito |
|---|---|---|
| 1 | a | 404 do Inativar/Reativar limpa as abas (`clearTheForm`) e avisa (`SubMenuMyResume.tsx`) |
| 2 | a | `GetData` tira `hash` e `email` dos registros; teste `theReadingDoesNotCarryTheInternalFields` |
| 3 | a | 409 saiu de `cached` para `callbacks` nas 4 requisições (`ServerRequests.ts`) |
| 4 | a | `ChangeStatus` com uma leitura só (`CcpGetEntityId`) |
| 5 | b | siglas mantidas |

Conferido no Chrome em 2026-10-15, com um candidato novo (`navegador.1792101852344@teste.com`) e a API vis reiniciada:

| # | O que foi feito na tela | Resultado |
|---|---|---|
| 1 | excluir pela API (outra janela) e clicar em Inativar | faixa "sem currículo", toast "Currículo não encontrado", abas limpas |
| 2 | `GET /resume/{email}` | 14 campos, sem `hash` e sem `email` |
| 3 | 409 com sessão aberta, logout no servidor, novo login na mesma página | 1º "Desbloqueie seu login"; 2º só a senha; 409 fora do `localStorage` |
| 4 | Inativar e Reativar | toasts certos; registro passou para a gêmea e voltou |

---

## 1. Currículo excluído em outra janela (R05-1)

**Como acontece:**

1. O candidato abre a tela "Ver meu currículo" em duas abas do navegador, A e B. As duas mostram "Currículo ativo" e as abas preenchidas.
2. Na aba A, ele clica em **Excluir** e confirma. O currículo é apagado de vez.
3. A aba B não fica sabendo: continua mostrando "Currículo ativo" e os dados.
4. Na aba B, ele clica em **Inativar**. O servidor responde 404 ("não existe currículo").

**O que a tela faz hoje com o 404:**

| Parte da tela | Fica assim |
|---|---|
| Faixa do topo | "Você ainda não tem currículo salvo" (certo) |
| Abas | continuam com todos os dados apagados (errado) |
| Aviso | nenhum (errado) |

**Por que é problema:**

- O candidato não entende por que a inativação "virou" ausência de currículo.
- As abas parecem salvas, mas não estão.
- Se ele clicar em "Salvar dados", o currículo que acabou de excluir é criado de novo.

| Opção | O que muda |
|---|---|
| a | limpar as abas, como o Excluir já faz, e avisar "Seu currículo não existe mais: ele foi excluído em outra janela" |
| b | só mostrar o aviso, mantendo os dados nas abas |
| c | deixar como está |

**Recomendação: a.** A tela fica coerente com o servidor e o candidato sabe o que houve.

## 2. A leitura do currículo devolve dados internos (R05-2)

**Como acontece:** toda vez que o candidato abre a tela, ela pede ao servidor o currículo gravado (`GET /resume/{email}`).

**O que vem na resposta, além dos campos do currículo:**

| Campo | O que é |
|---|---|
| `hash` | 45 chaves internas que o sistema usa para encaixar o currículo nas buscas dos recrutadores |
| `email` | o e-mail em forma de hash (a tela já conhece o e-mail legível) |

**Por que é problema:**

- A tela não usa nenhum desses dois campos.
- Eles mostram, a quem olhar a resposta no navegador (F12), como o sistema monta os agrupamentos internos.
- A resposta fica maior sem necessidade.

É o mesmo espírito da decisão 3b de 2026-10-15 (achado 25): a resposta deve levar só o que o front usa.

| Opção | O que muda |
|---|---|
| a | a leitura devolve só os campos que a tela usa |
| b | deixar como está |

**Recomendação: a.**

## 3. O modal de login usa uma resposta antiga (R05-3)

**Contexto:** o sistema permite uma sessão por vez. Se você tenta entrar enquanto já existe uma sessão aberta (em outro navegador, por exemplo), o servidor responde 409, "já há um login corrente". O modal então pede para desbloquear o login com um token enviado por e-mail.

**O defeito:** o modal guarda essa resposta 409 no navegador (`localStorage`, chave `logins`, em `app/JnAjax.js`). Da próxima vez que o login for pedido, ele reaproveita o 409 guardado, **sem perguntar de novo ao servidor**.

**Como aconteceu no teste:**

1. Havia uma sessão aberta, e a tentativa de login recebeu o 409, que ficou guardado.
2. Depois a sessão foi encerrada de verdade no servidor.
3. Uma nova ação pediu login. O modal foi direto para "Desbloqueie seu login", porque usou o 409 guardado.
4. O certo seria pedir só a senha, já que não havia mais conflito.

**Na prática:** quem saiu do sistema em outro aparelho e volta a este navegador é obrigado a esperar um token por e-mail, sem necessidade. Só depois de limpar o `localStorage` o modal pediu a senha normalmente.

| Opção | O que muda |
|---|---|
| a | não guardar o 409: o modal pergunta ao servidor toda vez |
| b | guardar o 409 por pouco tempo (alguns minutos) |
| c | deixar como está |

**Recomendação: a.** O conflito de sessão muda a qualquer momento, então só o servidor sabe a situação atual.

## 4. Inativar e reativar vão ao banco duas vezes (R05-4)

**Como acontece:** quando o candidato clica em Inativar ou Reativar, o servidor (`VisServiceResume.ChangeStatus`) precisa descobrir onde o currículo está hoje:

| Passo | Pergunta ao banco |
|---|---|
| 1 | o currículo está entre os ativos? (`exists`) |
| 2 | se não, está entre os inativos? (`exists`) |

**Por que é problema:** é exatamente o caso proibido pela regra FSED (registrada em 2026-10-15). Dois `exists` no mesmo fluxo devem virar uma consulta só pela fluent interface (`CcpGetEntityId`), que responde as duas perguntas numa ida ao banco.

O candidato não percebe nada: a tela funciona. É uma questão de desempenho e de seguir a regra.

| Opção | O que muda |
|---|---|
| a | corrigir agora, com uma ida ao banco |
| b | deixar para depois |

**Recomendação: a.** A regra já foi decidida; falta só autorizar a mudança.

## 5. Siglas de duas letras

**Contexto:** em 2026-10-15 as regras de arquitetura do `CLAUDE.md` ganharam siglas, para serem citadas como "isso fere a FSED".

**A questão:** seis siglas têm só duas letras:

| Sigla | Regra |
|---|---|
| ED | Entity Decorators |
| VE | Versionable Entity |
| CE | Cache Entity |
| AE | Async Entity |
| DL | Dto Less |
| NL | Null Less |

Siglas curtas se confundem mais com palavras comuns ou entre si numa conversa (por exemplo, "DL" pode virar "DLV").

| Opção | O que muda |
|---|---|
| a | alongar para três letras e atualizar o `CLAUDE.md` |
| b | manter como estão |

**Recomendação: b.** Elas já estão registradas e em uso, e nenhuma se repete.

---

## Para conferir

| O quê | Onde |
|---|---|
| Aviso de LinkedIn compartilhado do passo 2.9 (endereço `roteiro05-ti-593167`) | chat do operador no Telegram |
| Mudanças de tela 4a (modal de sugestão sem o texto do currículo) | não testada no roteiro 05 (fora do escopo) |
