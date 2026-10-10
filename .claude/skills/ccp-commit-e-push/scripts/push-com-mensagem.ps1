# Roda o fazPushEmTodosProjetosLocais.bat respondendo sozinho aos três prompts dele: o "pause" do começo, a mensagem do
# commit (set /p) e o "pause" do fim. As respostas vão por um arquivo de entrada em UTF-8 com a console em 65001, para
# que acentos cheguem inteiros ao git commit. Uso:
#   push-com-mensagem.ps1 -Message "texto" [-Bat <caminho do .bat>] [-Log <arquivo>]
param(
	[Parameter(Mandatory = $true)][string]$Message,
	[string]$Bat = 'C:\eclipse-workspaces\ccp\fazPushEmTodosProjetosLocais.bat',
	[string]$Log = (Join-Path $env:TEMP ('push-' + (Get-Date).ToString('yyyy-MM-dd_HHmmss') + '.log'))
)

# caracteres que quebram o .bat: aspas fecham o -m "...", ! some com o enabledelayedexpansion, % vira variável, e os
# demais são operadores do cmd
$proibidos = [regex]'["!%^&|<>]'
if ($proibidos.IsMatch($Message)) { throw "A mensagem não pode ter nenhum destes caracteres: `" ! % ^ & | < >" }
if ($Message -match "[\r\n]") { throw 'A mensagem precisa ter uma linha só' }
if (-not $Message.Trim()) { throw 'Mensagem vazia' }
if (-not (Test-Path $Bat)) { throw "Não achei o $Bat" }

$entrada = Join-Path $env:TEMP ('push-entrada-' + [guid]::NewGuid() + '.txt')
# linha 1: o pause do começo; linha 2: a mensagem; linha 3: o pause do fim
[IO.File]::WriteAllText($entrada, "`r`n$Message`r`n`r`n", (New-Object Text.UTF8Encoding $false))
try {
	$pasta = Split-Path $Bat -Parent
	# o git escreve o progresso do push na saída de erro: cada linha vira um ErrorRecord, mostrado pelo texto dele
	& cmd.exe /d /c "chcp 65001 >nul & cd /d `"$pasta`" & call `"$Bat`" < `"$entrada`"" 2>&1 |
		ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" } } |
		Where-Object { $_ -ne 'System.Management.Automation.RemoteException' } |
		Tee-Object -FilePath $Log
	Write-Host "LOG: $Log"
} finally {
	Remove-Item $entrada -Force -ErrorAction SilentlyContinue
}
