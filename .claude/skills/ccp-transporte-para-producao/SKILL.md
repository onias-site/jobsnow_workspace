---
name: ccp-transporte-para-producao
description: Regra do transporte para produção do JobsNow. Aplique sempre que uma alteração local precisar chegar à produção, que já existe desde 2026-11-01 e não passa por reset do Elasticsearch. Gatilhos - (1) inserir, alterar ou apagar registros, ou mudar o getFirstRecordsToInsert, de uma entidade de configuração (templates de e-mail e Telegram, parâmetros de envio, JnEntitySystemMessage, comandos e passos do bot, jb_bot, JnEntitySessionValidator, JnEntityWriteEventSubscribers, VisEntitySkill, VisEntitySkillDictionary, carga das vagas do Telegram); (2) renomear ou mover de pacote uma classe, um tipo aninhado ou um item de enum cujo nome fica gravado num registro (templateId, business, passo do bot, nome da mensagem do sistema); (3) criar ou eliminar uma entidade ou uma gêmea; (4) acrescentar, retirar ou mudar o tipo de um campo de entidade; (5) antes e depois de qualquer deploy. Exige um script em documentation/deploy e a checagem scripts/checar-producao.py.
---

# Transporte para produção

Produção existe desde 2026-11-01 e **nunca é recriada**: o `CcpCreateEntities` e as sementes do `getFirstRecordsToInsert` só valem para o ES local, que é descartável. Uma mudança de dado ou de estrutura feita aqui **não chega sozinha** à produção. Ou ela vai por um script numerado em `documentation/deploy`, ou produção diverge do código.

Esta skill não é um comando. É a regra que se aplica sempre que uma alteração cair num dos casos abaixo. Ao terminar a alteração local, o trabalho só está completo com o script de produção escrito e citado na resposta.

## As três obrigações

### 1. Dado de entidade de configuração vai para produção

Inserir, alterar ou apagar um registro numa entidade de regra `igual`, `adaptar`, `merge` ou `carga` em [entidades.tsv](entidades.tsv) exige um script que leve a mudança, com o mesmo `_id` do local. Isso vale também quando a mudança é só no seed do código, porque o seed não roda em produção. Exemplos: uma mensagem nova em `JnEntitySystemMessage`, um texto de template, um comando novo do bot.

| Regra | O que o script faz | Entidades |
|---|---|---|
| `igual` | copia da origem para o destino, sobrescrevendo | templates de e-mail e Telegram, `jn_system_message`, os 8 `jn_bot_command*` e `jn_bot_update_handler`, `jb_bot`, `jb_bot_explanation`, `jn_session_validator`, `jn_write_event_subscribers`, `vis_skill_dictionary` |
| `adaptar` | copia, mas os campos de ambiente recebem o valor de produção | `jn_email_parameters_to_send` (`sender`, `moreParameters`), `jn_instant_messenger_parameters_to_send` (`chatId`, `moreParameters`), `jb_bot_allowed_user` (`allowedUser`) |
| `merge` | só acrescenta ou atualiza, nunca substitui o índice (produção também escreve nele) | `vis_skill` (aprovações do operador), `vis_recruiter` e `vis_inactive_recruiter` (cadastro, inativação e reativação) |
| `carga` | vai em bloco, com os grupos do `jn_grouper`, pela sequência dos scripts 10, 11 e 21 | `vis_telegram_position`, `vis_statis_skill_line_chart`, `vis_statis_skill_pie_chart` |
| `nao-levar` | nada: produção é a fonte da verdade | dado do usuário, decisões do operador, estado do bot e dos processos, logs, histórico de envio, supressões do provedor, mecânica dos decorators |

Uma entidade fica em `nao-levar` quando o registro nasce de uma ação do usuário final ou quando é escrito por terceiros (operador, provedor, processo agendado), mesmo que fale do usuário. Exemplos: `JnEntityCommandNotAllowedToUser`, `JnEntityEmailSuppressed`, `VisEntityRecruiterFirstEmail`.

### 2. Renomeio de classe gravada em registro exige script

Vários registros guardam o nome de uma classe, de um tipo aninhado (`Outer$Inner`) ou de um item de enum (`Classe.item`), e o código executa ou procura esse nome:

- `templateId` e `subjectType` dos templates e parâmetros;
- `business` do `jn_session_validator` e do `jn_bot_update_handler`;
- o motor dos passos em `jn_bot_command_step`;
- os assinantes de `jn_write_event_subscribers`;
- `systemMessageName` da `jn_system_message`.

Em produção, renomear ou mover uma dessas classes deixa o nome antigo gravado. Depois do deploy, o `Class.forName` ou a busca pelo id falha em toda requisição que depende dele: a validação da sessão na vis, um passo do bot, o envio de um e-mail.

Ao renomear ou mover qualquer classe, tipo aninhado ou item de enum do projeto, procure o nome antigo nos seeds e nos registros. Se aparecer, escreva o script que regrava os registros de produção, recalculando o `_id` quando o nome fizer parte da chave (AEI), e rode-o **junto com o deploy**: antes, a API antiga quebraria; depois, a nova quebra até ele rodar.

### 3. Entidade criada ou eliminada exige script

- **Entidade ou gêmea nova:** o script cria o índice em produção com o mapeamento do local (`GET /<indice>/_mapping` depois de recriar as entidades locais, ou o arquivo de `ccp_rest-api-tests_jobsnow/documentation/<centro>/database/elasticsearch/scripts/entities/create/<indice>`). Se a entidade tiver seeds, o script grava também os seeds, e a linha nova entra no [entidades.tsv](entidades.tsv) com a sua regra. Ele roda antes do deploy da API que usa o índice.
- **Entidade eliminada:** o script apaga o índice de produção (e o da gêmea) **depois** de conferir que o snapshot do dia existe no `gs://jobsnow-backup`, e a linha sai do [entidades.tsv](entidades.tsv). Ele roda depois do deploy da API que não usa mais o índice.
- **Campo novo, retirado ou com tipo mudado:** os índices são `dynamic: strict`, então um campo sem mapeamento em produção faz a escrita falhar lá. Campo novo vai por `PUT /<indice>/_mapping`, como fez o script 13 com `origin`. Tipo mudado não muda no lugar: exige reindexar.

## Como escrever o script

Siga o padrão dos scripts existentes (16, 19, 20 e 24 são bons modelos):

- Nome `documentation/deploy/NN-<assunto>.py`, com o próximo número livre e um cabeçalho em comentário que diz o que faz, por que e o uso.
- O destino padrão é `http://127.0.0.1:9210` (túnel de produção), com a autenticação em `ES_DESTINO_AUTH`. A origem, quando há, é o ES local `http://127.0.0.1:9200`.
- O script é idempotente (rodar de novo não estraga nada) e grava com o mesmo `_id` do local.
- Ele confere o que gravou e imprime o resultado.
- O cache das entidades dura 1 hora. Depois do script, publique nova revisão das APIs do Cloud Run e reinicie os consumidores do PM2, ou espere a hora passar. Diga isso ao usuário.
- Teste o script contra o ES local antes, quando fizer sentido. A execução em produção pelo túnel fica com o usuário, salvo ordem dele.

## Checagem automática

[scripts/checar-producao.py](scripts/checar-producao.py) só lê e não grava em nenhum ES:

```bash
ES_DESTINO_AUTH=<valor> python -X utf8 .claude/skills/ccp-transporte-para-producao/scripts/checar-producao.py [destino] [origem]
```

| Passo | Confere |
|---|---|
| 0 | se toda entidade e gêmea do código tem linha no `entidades.tsv`, e vice-versa |
| 1 | os índices do código (configuradores `(Jn\|Vis\|Jb\|Js)Entity*` e suas `twinEntityName`) contra os do destino: falta criar, falta apagar |
| 2 | o mapeamento da origem contra o do destino: campo faltando, campo sobrando, tipo diferente. Objeto `dynamic: true` (`json`, `headers`, `moreParameters`) conta como um campo só: os subcampos que os dados criaram em cada ES não entram. Campo que falta vai pelo script 43 |
| 3 | toda string `com.(ccp\|jn\|vis\|jb\|js)...` gravada nos índices com `varrer_classes=sim`: precisa existir no código como classe, tipo aninhado ou item de enum. Se não existir, é renomeio sem script |
| 4 | os registros das entidades levadas: faltando, diferentes (ignorando os campos de ambiente do `adaptar`) ou sobrando. No `merge` só aponta o que falta; na `carga` compara contagens |

Ele sai com 1 quando há pendência. Rode a checagem:

- antes de cada `/ccp-deploy`, para saber quais scripts ainda faltam rodar;
- depois de rodar os scripts, para confirmar que não sobrou nada;
- sempre que esta skill disparar e o túnel estiver aberto.

Sem o túnel, rode com o destino igual à origem (`http://127.0.0.1:9200 http://127.0.0.1:9200`) para validar só os passos 0 e 3 contra o código.

Em 2026-11-03, rodando local contra local, o passo 1 já aponta seis índices que sobraram no ES local sem entidade no código: `jn_async_task`, `jn_email_reported_as_spam`, `jn_filas`, `jn_login_session_token_attempts`, `jn_login_token_attempts` e `js_login_email`. Se algum deles existir em produção, também precisa de script de remoção.

## Manutenção desta skill

Toda entidade nova entra no [entidades.tsv](entidades.tsv) com a regra decidida (pergunte ao usuário se não for óbvio) e `varrer_classes=sim` quando algum campo guardar nome de classe. Toda entidade eliminada sai dele. O passo 0 da checagem acusa o esquecimento.
