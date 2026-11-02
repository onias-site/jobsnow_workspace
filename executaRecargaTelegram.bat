@echo off
setlocal

rem Recalcula tudo o que vem dos anuncios do Telegram, para vagas antigas enxergarem skills novas ou regras de texto novas:
rem APAGA vis_telegram_position, os graficos, os grupos de estatistica e as copias do descartavel e rele todos os arquivos
rem com o executaCargaTelegram.bat, que recalcula as estatisticas e o ranking de vis_skill no final.
rem Os arquivos nunca sao excluidos aqui. Nada e apagado de vis_recruiter nem de vis_skill.
rem Precisa do Elasticsearch local no ar. Os modulos entram pelos jars do ~/.m2: depois de mudar codigo, rode antes
rem "mvn -o install -DskipTests" nos modulos alterados (ou o buildEmTodosOsProjetos.bat).
rem Se a recarga parar no meio, rode de novo: os dados sao apagados e relidos desde o comeco.
rem Uso:
rem   executaRecargaTelegram.bat                 le C:\z com 8 threads
rem   executaRecargaTelegram.bat C:\outra 4      outra pasta e outro numero de threads

set "FOLDER=%~1"
if "%FOLDER%"=="" set "FOLDER=C:\z"
set "THREADS=%~2"
if "%THREADS%"=="" set "THREADS=8"
set "ES=http://localhost:9200"
set "OPTIONS=_delete_by_query?refresh=true&conflicts=proceed"

dir /b /a-d "%FOLDER%\*.htm*" "%FOLDER%\*.txt" >nul 2>nul
if errorlevel 1 (
    echo Nenhum arquivo .html, .htm ou .txt em %FOLDER%: nada foi apagado.
    endlocal
    exit /b 1
)

curl -s -f -o nul "%ES%"
if errorlevel 1 (
    echo Elasticsearch fora do ar em %ES%: nada foi apagado.
    endlocal
    exit /b 1
)

echo Compilando ccp_rest-api-tests_jobsnow...
pushd "%~dp0ccp_rest-api-tests_jobsnow"
call mvn -o -q test-compile
set "COMPILED=%ERRORLEVEL%"
popd
if not "%COMPILED%"=="0" (
    echo Falha na compilacao do Maven: nada foi apagado.
    endlocal
    exit /b 1
)

echo.
echo Isto vai APAGAR as vagas do Telegram e as estatisticas e reler os arquivos de %FOLDER%.
echo Sem os arquivos de TODAS as cargas anteriores nessa pasta, as vagas deles se perdem.
set "CONFIRMATION="
set /p "CONFIRMATION=Digite APAGAR para continuar: "
if not "%CONFIRMATION%"=="APAGAR" (
    echo Cancelado: nada foi apagado.
    endlocal
    exit /b 1
)

echo Apagando as vagas e os graficos...
curl -s -S -f -X POST "%ES%/vis_telegram_position,vis_statis_skill_line_chart,vis_statis_skill_pie_chart/%OPTIONS%" -H "Content-Type: application/json" -d "{\"query\":{\"match_all\":{}}}"
if errorlevel 1 goto :failed
echo.

echo Apagando os grupos de estatistica...
curl -s -S -f -X POST "%ES%/jn_grouper/%OPTIONS%" -H "Content-Type: application/json" -d "{\"query\":{\"terms\":{\"parentName\":[\"vis_statis_skill\",\"vis_statis_skill_line_chart\",\"vis_statis_skill_pie_chart\"]}}}"
if errorlevel 1 goto :failed
echo.

echo Apagando as copias do descartavel...
curl -s -S -f -X POST "%ES%/jn_disposable_record/%OPTIONS%" -H "Content-Type: application/json" -d "{\"query\":{\"term\":{\"entity\":\"vis_telegram_position\"}}}"
if errorlevel 1 goto :failed
echo.

call "%~dp0executaCargaTelegram.bat" "%FOLDER%" %THREADS% manter
set "RESULT=%ERRORLEVEL%"
endlocal & exit /b %RESULT%

:failed
echo Falha ao apagar os dados: rode de novo. Os arquivos continuam em %FOLDER%.
endlocal
exit /b 1
