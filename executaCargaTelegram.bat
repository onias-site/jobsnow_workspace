@echo off
setlocal

rem Carga dos anuncios do Telegram (.html/.htm) e do WhatsApp (.txt, todas as vagas como home office), sem IA em nenhuma
rem etapa: grava as vagas em vis_telegram_position (em threads), carrega os recrutadores, recalcula as estatisticas e o
rem ranking de vis_skill e EXCLUI os arquivos lidos e confirmados no indice.
rem Nada e apagado de vis_telegram_position nem de vis_recruiter: a carga so acrescenta, e repetir um arquivo nao duplica.
rem Precisa do Elasticsearch local no ar. Os modulos entram pelos jars do ~/.m2: depois de mudar codigo, rode antes
rem "mvn -o install -DskipTests" nos modulos alterados (ou o buildEmTodosOsProjetos.bat).
rem Uso:
rem   executaCargaTelegram.bat                   le C:\z com 8 threads e exclui os arquivos confirmados
rem   executaCargaTelegram.bat C:\outra 4        outra pasta e outro numero de threads
rem   executaCargaTelegram.bat C:\z 8 manter     nao exclui nenhum arquivo

set "FOLDER=%~1"
if "%FOLDER%"=="" set "FOLDER=C:\z"
set "THREADS=%~2"
if "%THREADS%"=="" set "THREADS=8"

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

echo Executando a carga de %FOLDER% com %THREADS% threads...
"C:\Program Files\Java\jdk-17\bin\java.exe" -Xmx6g -Dfile.encoding=UTF-8 @%ARG_FILE% ..\documentation\roteiros-de-teste\automacao\LoadTelegramPositions.java "%FOLDER%" %THREADS% %3
set "RESULT=%ERRORLEVEL%"

popd
endlocal & exit /b %RESULT%
