---
name: ccp-curriculos-para-uma-vaga
description: Acha, entre os currículos ativos de produção, os compatíveis com o texto de uma vaga e envia aos e-mails dados o e-mail de currículos aos recrutadores (o mesmo do envio diário) só com esses currículos, com a abertura trocada pelo texto da vaga e com o assunto dado. Uso - /ccp-curriculos-para-uma-vaga assunto="<assunto>" emails=<e-mail>[,<e-mail>...] vaga=<texto da vaga>
disable-model-invocation: true
---

# Currículos de produção para uma vaga

Parâmetros, todos obrigatórios:

| Parâmetro | Conteúdo |
|---|---|
| `assunto` | o assunto do e-mail que o recrutador recebe, usado como veio |
| `emails` | um ou mais destinatários, separados por vírgula |
| `vaga` | o texto da vaga, normalmente tudo depois de `vaga=`, com várias linhas |

Se faltar algum, mostre o uso em uma linha e não rode nada. Os e-mails passados aqui já são a autorização de envio: não pergunte de novo.

**Só produção:** tudo é lido de produção pelo túnel e o e-mail sai pelo SendGrid de produção. Nada é gravado em produção: nem a marca de "já enviado hoje" nem a lista "Ver todos". Por isso o envio diário das 10:00 não é afetado.

## Passos

Pasta de trabalho: `C:\logs\curriculos-para-vagas\<aaaa-mm-dd-hhmm>\`. Ela fica como registro do envio.

1. **Entrada.** Grave com a ferramenta Write, nunca pelo Bash (acentos quebram o Bash):
   - `vaga.txt`: o texto da vaga, como veio;
   - `assunto.txt`: o assunto.
2. **Listar.** Rode, com timeout de 400000 ms:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File C:\eclipse-workspaces\ccp\.claude\skills\ccp-curriculos-para-uma-vaga\scripts\curriculos-para-uma-vaga.ps1 -Etapa listar -Pasta <pasta>
   ```
   Grava `curriculos-ativos.json`. Cada item traz:
   - linkedin, desiredJob, lastJob, resumeType;
   - years: anos de experiência, calculados como no e-mail;
   - clt, pj, ddd;
   - skills: só as que o sistema não descarta;
   - notAllowedCompany, restricted, invalidLinkedin.
3. **Escolher.** Leia o JSON e compare cada currículo com a vaga:
   - **Núcleo da vaga:** as tecnologias e funções que a definem (ex.: Dynamics 365, Power Platform).
   - **Obrigatórios:** os itens listados como obrigatórios.
   - **Experiência e contratação:** os anos pedidos e o tipo de contratação (PJ/CLT, pelo campo de pretensão).
   - **Região:** vaga remota não elimina ninguém. Vaga presencial pede o DDD da cidade ou o 10 (home office) fora.
   - **Coincidência fraca não conta:**
     - um nome parecido (Dynamics AX não é Dynamics 365 CRM);
     - uma skill que o candidato marcou como evitada;
     - uma sigla genérica (CRM) junto de uma pilha distante.
   - **Retire sempre:**
     - `invalidLinkedin`: o currículo dá 410;
     - `restricted`: o link "Ver currículo" dá 404;
     - quem tem o domínio do destinatário em `notAllowedCompany`.

   Nenhum compatível: diga isso, com os que chegaram mais perto e o motivo, e não envie.
4. **Gravar a escolha.** Grave em `linkedins.txt` um LinkedIn por linha, exatamente como vem no campo linkedin do JSON.
5. **Simular.** Rode a mesma linha de comando com `-Etapa simular -Emails <e1>,<e2>`. Confira na `previa-1.html`:
   - a abertura com a vaga;
   - o assunto, na primeira linha, como comentário;
   - um link `ver-curriculo` por currículo;
   - nenhum `{campo}` sem preencher.
6. **Enviar.** Rode com `-Etapa enviar -Emails <e1>,<e2>`. Cada destinatário sai com `OK enviado linhas=N`. Destinatário suprimido no SendGrid (`jn_email_suppressed`) é pulado (`SUPRIMIDO`, saída 4).

A linha "curriculos: N de M (restritos e LinkedIn invalido fora)" vem do leitor oficial reaproveitado. Aqui o filtro é a lista de LinkedIns escolhidos.

## O e-mail

- **Corpo:** é o template de produção `VisMessages$VisNotifyRecruiterAboutResumes` (português). As frases de abertura, do início até o aviso amarelo, são trocadas por:

  `Boa tarde, abaixo a lista de curriculos para a vaga que você me enviou a pouco <br/>` + a vaga (`montar-abertura.py`)

  O resto do template fica igual: aviso, descadastro, tabela, dica de abordagem e rodapé.
- **Assunto:** o dado em `assunto.txt`.
- **Linhas e links:** linhas, ordem, links assinados do "Ver currículo" (por destinatário), tabela, cabeçalhos List-Unsubscribe e link de descadastro seguem o processo diário (`VisBusinessSendResumesToRecruiters`, chamado por reflexão em `SendJobResumes.java`).
- **Destinatário:** não precisa estar em `vis_recruiter`. Se ele abrir um currículo, a visualização é gravada e ele vira (ou volta a ser) recrutador ativo.

## Resposta

1. Uma grade dos currículos escolhidos (skill `ccp-exibir-em-tabela`) com #, núcleo da vaga atendido, obrigatórios atendidos, anos e PJ.
2. Os LinkedIns como links clicáveis numa tabela Markdown, com o texto decodificado e o endereço codificado. É a exceção à grade: no bloco de código o terminal não abre o link.
3. Uma grade por destinatário com as linhas enviadas e o resultado do SendGrid.
4. O caminho da pasta de trabalho.

Nunca imprima valores de `producao.json`.

## Limites

- **Escolha:** é julgamento sobre texto livre. Diga o critério usado e os que ficaram de fora por pouco.
- **Leitor oficial:** se o filtro do `ler-curriculos-de-producao.py` mudar, `ler-curriculos-escolhidos.py` para com uma mensagem. Atualize o texto procurado.
- **Template:** se o template de produção mudar e não houver mais `<p style="background-color` depois de `<body>`, o executor para com "template de producao mudou".
