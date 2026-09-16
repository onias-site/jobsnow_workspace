@echo off
pause
setlocal enabledelayedexpansion
set /p commit_message=Digite a mensagem do commit:

rem Garante que tudo roda a partir da pasta do proprio script (a pasta de trabalho)
pushd "%~dp0."

rem --- Repositorio da pasta de trabalho: arquivos globais comuns a todos os projetos ---
if exist ".git" (
    echo Executando comandos Git em: !CD! [workspace]
    git add .
    git commit -m "!commit_message!"
    git push
    echo Fez !CD!
)

rem --- Repositorios dos projetos ---
for /d /r %%i in (*) do (
    pushd "%%i"
    if exist ".git" (
        echo Executando comandos Git em: %%i
        git add .
        git commit -m "!commit_message!"
        git push
        echo Fez %%i
    )
    popd
)

popd
echo Terminou.
pause
