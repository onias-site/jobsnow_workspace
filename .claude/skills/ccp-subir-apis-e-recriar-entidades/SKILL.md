---
name: ccp-subir-apis-e-recriar-entidades
description: Sobe (ou reinicia) as APIs locais fora do Eclipse — jn na porta 8080 e vis na 8081 — e executa com.ccp.random.CcpCreateEntities.main (recriação dos índices do Elasticsearch local) pelo executaCcpCreateEntities.bat. Use quando pedirem "subir as APIs", "reiniciar as APIs e recriar as entidades", "rodar o CcpCreateEntities", "recriar os índices", ou quando o build do Eclipse estiver com problema e for preciso rodar o ambiente local por fora dele.
---

# Subir as APIs 8080/8081 e executar o CcpCreateEntities

Tudo roda fora do Eclipse, com o classpath montado pelo Maven a partir dos jars do `~/.m2`.

## Passos

Use a scratchpad da sessão como `<scratch>` para classpaths e logs.

1. **Parar o que estiver nas portas 8080 e 8081.** Ache os PIDs com
   `Get-NetTCPConnection -LocalPort 8080,8081 -State Listen` e pare com `Stop-Process -Force`.
   Se o processo for `javaw.exe`, a API está rodando no Eclipse (talvez em debug). Avise o usuário
   antes de parar. Os avisos "failed" das tarefas em segundo plano que tinham subido as APIs
   antigas são esperados: vêm do processo que acabou de ser parado.

2. **Subir as duas APIs**, cada uma com o Bash em `run_in_background` e com a pasta de trabalho no
   módulo da API (o classpath começa por `target/classes`, que é relativo):

   ```bash
   cd /c/eclipse-workspaces/ccp/jn_rest-api_spring_jobsnow_dependency-chooser \
     && mvn -o -q compile dependency:build-classpath -Dmdep.outputFile=<scratch>/jn-api-cp.txt \
     && "C:/Program Files/Java/jdk-17/bin/java" -cp "target/classes;$(cat <scratch>/jn-api-cp.txt)" \
        com.jn.rest.api.JnRestApiSpringStarter > <scratch>/jn-api.log 2>&1
   ```

   Para o vis, use o mesmo comando com `vis_rest-api_spring_jobsnow_dependency-chooser`,
   `vis-api-cp.txt`, `com.vis.rest.api.VisRestApiSpringStarter` e `vis-api.log`. Rode os dois
   comandos na mesma resposta.

3. **Conferir.** Aguarde alguns segundos (a compilação do Maven vem antes da subida). Depois peça
   `http://localhost:8080/rota/inexistente` e `http://localhost:8081/rota/inexistente`: as duas
   APIs no ar respondem **404**. Se alguma porta não abrir, leia o `<scratch>/*-api.log`.

4. **Executar o CcpCreateEntities** com o `.bat` da raiz, em segundo plano:

   ```powershell
   & cmd /c "C:\eclipse-workspaces\ccp\executaCcpCreateEntities.bat" *> "<scratch>\create-entities.log"
   ```

   Ele compila `ccp_rest-api-tests_jobsnow` (`mvn -o test-compile`), monta o classpath de teste
   num arquivo de argumentos do java (o classpath passa de 18 mil caracteres) e roda o `main` com a
   pasta de trabalho no projeto de testes. **O `main` abre um diálogo Swing**: diga ao usuário que
   marque os centros de custo (jn, vis, jb) na tela dele. Cancelar ou fechar o diálogo não recria nada.
   Recriar só o jn apaga os templates que o vis semeia em índices jn; para restaurá-los, marque o vis
   também. Quando terminar, leia o log e os arquivos de erro em `c:\logs\<centro de custo>\`
   (`mappingJnEntitiesErrors.json`, `insertResults.json`).

5. **Informar** o PID de cada porta, os 404 de confirmação e o resultado do CcpCreateEntities. Lembre
   que as APIs subiram em segundo plano por esta sessão: elas param se a sessão for encerrada.

## Observações

- O código usado é o dos jars do `~/.m2`. Se o usuário alterou algum módulo, rode
  `mvn -o -q install -DskipTests` nesse módulo (ou o `buildEmTodosOsProjetos.bat`) **antes** do passo 1.
- Depois de recriar os índices do jn, o login do front some. Veja a memória
  `reference_login_after_es_reset` (limpar `logins` do localStorage).
