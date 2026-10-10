@echo off
setlocal

rem Executa com.ccp.random.CcpCreateEntities.main fora do Eclipse.
rem Compila o projeto de testes com o Maven (offline), monta o classpath de teste
rem e roda a classe com a pasta de trabalho em ccp_rest-api-tests_jobsnow, que e
rem de onde ela le os scripts em documentation\<centro de custo>\...
rem Os demais modulos entram pelos jars do ~/.m2: rode antes "mvn -o install -DskipTests"
rem nos modulos alterados (ou o buildEmTodosOsProjetos.bat) para usar o codigo atual.
rem O main abre um dialogo para escolher os centros de custo (jn, vis, jb) a recriar.

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

echo Executando CcpCreateEntities...
"C:\Program Files\Java\jdk-17\bin\java.exe" @%ARG_FILE% com.ccp.random.CcpCreateEntities
set "RESULT=%ERRORLEVEL%"

popd
endlocal & exit /b %RESULT%
