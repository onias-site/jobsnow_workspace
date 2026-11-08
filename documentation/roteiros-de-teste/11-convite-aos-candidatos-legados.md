# Roteiro 11 — Convite aos candidatos legados

> **Criado em 2026-11-07**, depois dos ajustes do convite (assunto, empresas indesejadas, link do formulário, habilidades depois da 15ª num link com `title`). Ainda não executado por inteiro: a simulação e a prévia a `onias85@gmail.com` rodaram durante os ajustes, por um executor temporário que deu origem ao modo `previa`.

## O que é

Envio único, feito no deploy, que convida cada dono de currículo do índice legado `profissionais2` a cadastrar o currículo no formulário novo. O e-mail mostra uma prévia de como o recrutador verá o currículo: a mesma tabela do e-mail aos recrutadores (roteiro 08), com uma linha montada com os dados do cadastro antigo.

| Peça | Onde |
|---|---|
| Regra do envio | `VisBusinessInviteLegacyCandidates` (vis) |
| Linha da tabela | `VisBusinessBuildLegacyCandidateTable`, que usa `VisBusinessBuildResumeRow` e `VisBusinessRenderResumesTable` |
| Template e parâmetros | `VisEntityRecruiterResumes.getInvitationSeeds` (`templateId` `com.vis.messages.VisMessages$VisInviteLegacyCandidate`), gravados pela própria automação a cada execução |
| Automação | `scripts/executaConviteDeCurriculos.bat`, que roda `automacao/InviteLegacyCandidates.java` |
| Controle do "uma vez só" | `C:\logs\convite-curriculos\convidados.txt`: o SHA-1 de cada e-mail aceito pelo SendGrid (formato do framework, com sinal: `-3987…`) |

## Regras

1. **Ficam de fora**, nesta ordem: e-mail inválido; quem já tem currículo, ativo ou inativo (`vis_resume` ou `vis_inactive_resume`); quem já foi convidado (`convidados.txt`); e-mail suprimido no SendGrid (`jn_email_suppressed`). Os inativos do legado (status 0) **recebem**.
2. **Só dado real na tabela:** pretensões CLT e PJ sempre ("Não Informada" quando falta); negociação só se o legado tiver `pretensaoNegociavel`; experiência só se o legado tiver o ano; disponibilidade só com um número de dias; PCD sempre. Viagem, temporário e idiomas **nunca** saem (o legado não tem). `mudanca` não vira regiões.
3. **Regiões:** o legado tem um DDD só. Com home office e DDD 0, a linha é "Aceita somente homeoffice"; senão, a região do DDD. Por isso o "+N regiões" **nunca** aparece no convite: ele é conferido no roteiro 08 (1.2) e no 05 (2.12).
4. **Habilidades:** só no tipo 1 (Tecnologia da Informação), lidas do texto do currículo antigo (`curriculo.t`) pelo mesmo `GetSkillsFromText` da tela, na ordem do ranking de `vis_skill`. As 15 primeiras aparecem; as outras ficam fora do e-mail, contadas pelo link **ver as outras N habilidades**, cujo `title` lista todas. O Gmail apaga `<details>`, por isso não há lista recolhida.
5. **Datas:** "Data de inserção" e "Última alteração" saem com a hora do envio. **Pendência de decisão do usuário** (2026-11-07): usar as datas reais do legado (`dataDeInclusao`, `dataDeAlteracao`), tirar as duas linhas ou explicar que serão as do cadastro novo. Até lá, o esperado é a hora do envio.
6. **Falha do provedor para tudo** (`THROWS`): só o e-mail aceito vai para `convidados.txt`, e rodar de novo continua de onde parou. O template é repetível (`JnRepeatableMessage`): quem garante o "uma vez só" é o arquivo, não o registro de envio.
7. **Chave do SendGrid:** nos modos `enviar` e `previa`, o `.bat` troca só a chave e o endereço do SendGrid pelos de `C:\segredos\producao.json` (`automacao/com-chave-do-sendgrid.ps1`), para o processo do Java. A chave da `application_properties` local dá 401. O Elasticsearch continua o local.
8. **O envio em massa não é testado** (regra 5 do roteiro 10). Aqui só rodam `simular` e `previa`.

## Modos da automação

Rodar na raiz do workspace:

| Comando | O que faz |
|---|---|
| `scripts\executaConviteDeCurriculos.bat simular` | 3 e-mails em `C:\logs\email`, links para `http://localhost:3000`; nada é registrado |
| `scripts\executaConviteDeCurriculos.bat simular 20` | o mesmo, com 20 |
| `scripts\executaConviteDeCurriculos.bat previa https://onias.site <e-mail do legado>` | SendGrid real, **só** para esse candidato; os outros contam como já convidados; nada é registrado |
| `scripts\executaConviteDeCurriculos.bat enviar https://onias.site [quantidade]` | o envio de verdade, fora deste roteiro |

A saída termina em `OK {...}` com os contadores: `legacyCandidates`, `invalidAddress`, `hasResume`, `invitedBefore`, `suppressed` e `emailsSent`. `invalidAddress`, `hasResume` e `invitedBefore` contam o índice inteiro; `suppressed` só conta os que o envio alcançou antes do limite.

## O que conferir fora da tela

| O que | Onde |
|---|---|
| E-mail simulado | `C:\logs\email\<e-mail>\com.vis.messages.VisMessages$VisInviteLegacyCandidate.html` (há também uma cópia em `C:\logs\email\`: N e-mails dão N+1 arquivos) |
| Assunto | o arquivo guarda só o corpo: `jn_email_template_message` com o `templateId` do convite |
| Documento legado | `http://localhost:9200/profissionais2/_doc/<e-mail>?_source_excludes=curriculo` (o campo `curriculo` inteiro traz o arquivo; peça só `curriculo.t`) |
| Convidados | `C:\logs\convite-curriculos\convidados.txt` (número de linhas antes e depois) |
| E-mail real | Gmail de `onias85@gmail.com`, inclusive o Spam |

## Pré-requisitos

- Elasticsearch local (9200) com o índice `profissionais2` (4.135 documentos em 2026-11-07).
- O texto `moreSkills` em `jn_system_message`, gravado pelas sementes do vis (`VisRecruiterResumesTexts`; depois de um reset, pelo `CcpCreateEntities` do vis). Sem ele, a tabela falha.
- Para a `previa`: `C:\segredos\producao.json` com a chave do SendGrid.

---

## C1 — Simulação

- [ ] 1.1 Anote o número de linhas de `convidados.txt`. Rode `simular`. Esperado: `emailsSent: 3`; três pastas novas (ou regravadas) em `C:\logs\email`; `convidados.txt` com o mesmo número de linhas.
- [ ] 1.2 Rode `simular` de novo. Esperado: os mesmos 3 candidatos (a simulação não marca ninguém como convidado).
- [ ] 1.3 Os contadores: `legacyCandidates` igual ao total do índice; `invalidAddress + hasResume + invitedBefore` menor que ele.

## C2 — Conteúdo do e-mail

Abra no navegador um e-mail do C1 (ou o da prévia, no C6). Esperado, nesta ordem:

- [ ] 2.1 Assunto "Envie seu currículo para 2.000 recrutadores gratuitamente". O convite sai sempre em português; o template em inglês existe, mas não é usado.
- [ ] 2.2 "Olá, aqui é o Onias, do JobsNow. Você cadastrou o seu currículo conosco há algum tempo.", com o nome ligado a `https://www.linkedin.com/in/onias85/`.
- [ ] 2.3 O parágrafo "O JobsNow foi refeito, e o seu cadastro antigo não aparece para os recrutadores do novo sistema..." e o botão **Cadastrar meu currículo** para `<endereço do front>/meus-dados/sobre-mim` (`http://localhost:3000` na simulação, `https://onias.site` na prévia; nunca `www.jobsnow.com.br`).
- [ ] 2.4 "No cadastro, você também pode informar as empresas para as quais não quer que o seu currículo seja enviado."
- [ ] 2.5 O título "Como o recrutador verá o seu currículo", o parágrafo da prévia ("feita com os dados do seu cadastro antigo...") e a tabela de uma linha, com as 5 colunas dos recrutadores.
- [ ] 2.6 "Este convite é único: se você não se cadastrar, não enviaremos outro e-mail sobre este assunto." e o rodapé com **Política de privacidade**, sem endereço.

## C3 — Só dado real na tabela

Compare a linha com o documento legado do mesmo e-mail.

- [ ] 3.1 "O que importa": CLT e PJ sempre; "Pretensões salariais negociáveis" só se houver `pretensaoNegociavel`; "Experiência em anos" só se houver `experiencia`; a região do DDD, ou "Aceita somente homeoffice" com home office e DDD 0; com DDD 0 e sem home office, nenhuma região.
- [ ] 3.2 "Outras Informações": disponibilidade só com `disponibilidade` maior que 0; "Pessoa com deficiência (PCD)" sempre; **nenhuma** linha de viagem, temporário ou idioma.
- [ ] 3.3 Tipos 2, 3 e 4 (`tipoVaga`): "Idiomas e habilidades" vazia. Um tipo 1 sem `curriculo.t` também sai vazio (os primeiros documentos do índice são assim: não é defeito).
- [ ] 3.4 "Datas e visualização": "Você nunca visualizou este currículo", **Ver currículo** como texto (sem link: o candidato ainda não tem currículo) e as duas datas com a hora do envio (regra 5).

## C4 — Mais de 15 habilidades

- [ ] 4.1 Use um tipo 1 com texto longo (`onias85@gmail.com` rende 109 habilidades em 2026-11-07). Esperado: 15 linhas, da mais pedida para a menos pedida no ranking de `vis_skill` (JAVA, JAVASCRIPT, SQL...), e o link **ver as outras 94 habilidades** para o formulário.
- [ ] 4.2 O `title` do link lista as 94 restantes, separadas por vírgula, na mesma ordem. Nenhuma delas aparece como linha, e o código-fonte não tem `<details>`.
- [ ] 4.3 Com 15 ou menos, nenhum link.

## C5 — Quem fica de fora

Cada passo compara os contadores com os do C1.

- [ ] 5.1 **Já tem currículo:** salve pela tela (roteiro 04) um currículo com o e-mail de um candidato legado. Rode `simular`. Esperado: `hasResume` sobe 1, e esse candidato não recebe. Inativar o currículo não muda nada (inativo também conta). Exclua o currículo depois.
- [ ] 5.2 **Suprimido:** grave em `jn_email_suppressed` um dos 3 candidatos que a simulação alcança. Rode `simular`. Esperado: `suppressed: 1`, e o quarto candidato entra no lugar dele. Apague o registro depois.
- [ ] 5.3 **E-mail inválido:** `invalidAddress` conta os documentos cujo `id` não é um e-mail válido (espaços nas pontas e maiúsculas não contam como inválido: o convite apara e põe em minúsculas).

## C6 — Prévia a um destinatário (SendGrid real)

- [ ] 6.1 Anote as linhas de `convidados.txt`. Rode `previa https://onias.site onias85@gmail.com`. Esperado: `emailsSent: 1`; `invitedBefore` = `legacyCandidates - invalidAddress - hasResume - 1` (na prévia, todos os outros contam como já convidados, e o `convidados.txt` nem é lido); `convidados.txt` com o mesmo número de linhas.
- [ ] 6.2 O e-mail chega ao Gmail com o remetente `curriculos@onias.site` e o conteúdo do C2, com os links para `https://onias.site`.
- [ ] 6.3 No Gmail do computador, passe o mouse em **ver as outras N habilidades**: a dica com a lista aparece (se não aparecer, o Gmail tirou o `title`; anote como achado). No celular, a dica não existe.
- [ ] 6.4 Rode a prévia com um e-mail que não está no legado. Esperado: `emailsSent: 0` e nenhum e-mail.
- [ ] 6.5 Rode a prévia com o e-mail de quem já tem currículo (o do 5.1, antes de excluí-lo). Esperado: `emailsSent: 0` (`hasResume` vale também para a prévia).

---

## Resumo do que este roteiro cobre

| Regra | Cenário |
|---|---|
| Simulação não registra e repete os mesmos candidatos | 1.1, 1.2 |
| Assunto, textos, link do formulário, empresas indesejadas, rodapé | C2 |
| Só dado real na tabela; datas com a hora do envio (pendência) | C3 |
| 15 habilidades e o link com `title`, sem `<details>` | C4 |
| Quem já tem currículo, suprimido e e-mail inválido ficam de fora | C5 |
| Prévia real a um destinatário, sem registrar | C6 |
| Envio em massa e retomada pelo `convidados.txt` | fora (regra 8) |
