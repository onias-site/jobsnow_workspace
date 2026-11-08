@echo off
setlocal

rem Convite unico aos candidatos do indice legado profissionais2: cada um recebe o link do formulario de curriculos e a
rem previa de como o recrutador vera o curriculo. Rodar uma vez, no deploy.
rem Precisa do Elasticsearch com o indice profissionais2. Para enviar, precisa tambem da chave do SendGrid.
rem Quem ja foi convidado fica em c:\logs\convite-curriculos\convidados.txt: rodar de novo continua de onde parou.
rem Uso:
rem   executaConviteDeCurriculos.bat simular                      3 e-mails em c:\logs\email, nada sai daqui
rem   executaConviteDeCurriculos.bat simular 20                   20 e-mails em c:\logs\email
rem   executaConviteDeCurriculos.bat enviar https://onias.site       envia a todos pelo SendGrid
rem   executaConviteDeCurriculos.bat enviar https://onias.site 100   envia no maximo 100 (para respeitar o plano)
rem   executaConviteDeCurriculos.bat previa https://onias.site fulano@x.com   so a esse candidato, sem registrar (roteiro 11)
rem O endereco e o do front de producao (https://onias.site): o link do formulario sai dele.
rem Em enviar e previa, a chave do SendGrid vem de C:\segredos\producao.json (a da application_properties local da 401),
rem por automacao\com-chave-do-sendgrid.ps1, so para o processo do java.

pushd "%~dp0..\ccp_rest-api-tests_jobsnow"

set "CP_FILE=target\create-entities-cp.txt"
set "ARG_FILE=target\create-entities-args.txt"

echo Compilando ccp_rest-api-tests_jobsnow e montando o classpath de teste...
call mvn -o -q test-compile dependency:build-classpath -Dmdep.outputFile=%CP_FILE% -Dmdep.includeScope=test
if errorlevel 1 (
    echo Falha na compilacao do Maven.
    popd
    endlocal
    exit /b 1
)

rem O classpath passa de 18 mil caracteres: vai num arquivo de argumentos do java (@arquivo).
powershell -NoProfile -Command "$cp = (Get-Content -Raw '%CP_FILE%').Trim() -replace '\\','/'; Set-Content -Encoding ascii '%ARG_FILE%' ('-cp \"target/test-classes;target/classes;' + $cp + '\"')"

set "RUNNER=..\documentation\roteiros-de-teste\automacao\InviteLegacyCandidates.java"
if /i "%~1"=="simular" (
    "C:\Program Files\Java\jdk-17\bin\java.exe" -Xmx4g -Dfile.encoding=UTF-8 @%ARG_FILE% %RUNNER% %*
) else (
    rem enviar e previa: a chave do SendGrid de C:\segredos, so neste processo
    powershell -NoProfile -ExecutionPolicy Bypass -File ..\documentation\roteiros-de-teste\automacao\com-chave-do-sendgrid.ps1 -Xmx4g -Dfile.encoding=UTF-8 @%ARG_FILE% %RUNNER% %*
)
set "RESULT=%ERRORLEVEL%"

popd
endlocal & exit /b %RESULT%
