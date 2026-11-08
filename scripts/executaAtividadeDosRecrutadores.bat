@echo off
setlocal

rem Datas de atividade dos recrutadores (vis_recruiter), que ordenam o e-mail diario de curriculos:
rem   lastTelegramAppearance = dia da mensagem mais recente do Telegram/WhatsApp com o e-mail, so se tiver ate 6 meses;
rem   lastLegacyView = visualizacao mais recente no JobsNow legado (indice visualizacao_de_curriculo, so no ES local).
rem Le os arquivos da pasta sem exclui-los e so grava data mais recente que a guardada: rodar de novo nao estraga nada.
rem Precisa do Elasticsearch local no ar. Os modulos entram pelos jars do ~/.m2: depois de mudar codigo, rode antes
rem "mvn -o install -DskipTests" nos modulos alterados (ou "mvn clean install" na raiz).
rem Uso:
rem   executaAtividadeDosRecrutadores.bat            le C:\z
rem   executaAtividadeDosRecrutadores.bat C:\outra   outra pasta

set "FOLDER=%~1"
if "%FOLDER%"=="" set "FOLDER=C:\z"

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

echo Lendo as aparicoes em %FOLDER% e as visualizacoes do legado...
"C:\Program Files\Java\jdk-17\bin\java.exe" -Xmx6g -Dfile.encoding=UTF-8 @%ARG_FILE% ..\documentation\roteiros-de-teste\automacao\LoadRecruitersActivity.java "%FOLDER%"
set "RESULT=%ERRORLEVEL%"

popd
endlocal & exit /b %RESULT%
