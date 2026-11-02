@echo off
setlocal

rem Convite unico aos candidatos do indice legado profissionais2: cada um recebe o link do formulario de curriculos e a
rem previa de como o recrutador vera o curriculo. Rodar uma vez, no deploy.
rem Precisa do Elasticsearch com o indice profissionais2. Para enviar, precisa tambem da chave do SendGrid.
rem Quem ja foi convidado fica em c:\logs\convite-curriculos\convidados.txt: rodar de novo continua de onde parou.
rem Uso:
rem   executaConviteDeCurriculos.bat simular                      3 e-mails em c:\logs\email, nada sai daqui
rem   executaConviteDeCurriculos.bat simular 20                   20 e-mails em c:\logs\email
rem   executaConviteDeCurriculos.bat enviar https://dominio       envia a todos pelo SendGrid
rem   executaConviteDeCurriculos.bat enviar https://dominio 100   envia no maximo 100 (para respeitar o plano)

pushd "%~dp0ccp_rest-api-tests_jobsnow"

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

"C:\Program Files\Java\jdk-17\bin\java.exe" -Xmx4g -Dfile.encoding=UTF-8 @%ARG_FILE% ..\documentation\roteiros-de-teste\automacao\InviteLegacyCandidates.java %*
set "RESULT=%ERRORLEVEL%"

popd
endlocal & exit /b %RESULT%
