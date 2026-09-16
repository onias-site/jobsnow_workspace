@echo off
pause
setlocal enabledelayedexpansion

rem Garante que tudo roda a partir da pasta do proprio script (a pasta de trabalho)
pushd "%~dp0."

rem --- Repositorio da pasta de trabalho: arquivos globais comuns a todos os projetos ---
if exist ".git" (
    echo Executando comandos Git em: !CD! [workspace]
    git reset --hard
    git pull
    echo Fez !CD!
)

rem --- Repositorios dos projetos ---
for /d /r %%i in (*) do (
    pushd "%%i"
    if exist ".git" (
        echo Executando comandos Git em: %%i
		git reset --hard
		git pull
        echo Fez %%i
    )
    popd
)

popd
echo Terminou.
pause
