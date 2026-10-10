# Impressão digital do código medido pela cobertura: uma linha por módulo Maven do workspace (cada um é um repositório
# git), com o commit atual e um hash das alterações locais (arquivos editados, removidos e novos, pelo conteúdo).
# A raiz (jobsnow_workspace) e o front end ficam de fora: não entram na cobertura, e a raiz muda a cada rodada, porque
# o histórico da skill fica nela. Uso:
#   . code-fingerprint.ps1; Get-CodeFingerprint -Root <workspace>   -> texto com uma linha por módulo
param()

function Get-TextHash([string]$text) {
	$sha = [Security.Cryptography.SHA256]::Create()
	try {
		$bytes = [Text.Encoding]::UTF8.GetBytes($text)
		return ([BitConverter]::ToString($sha.ComputeHash($bytes)) -replace '-', '').Substring(0, 16)
	} finally { $sha.Dispose() }
}

function Get-CodeFingerprint([string]$Root) {
	$lines = New-Object System.Collections.Generic.List[string]
	$modules = Get-ChildItem $Root -Directory | Where-Object { (Test-Path (Join-Path $_.FullName 'pom.xml')) -and (Test-Path (Join-Path $_.FullName '.git')) } | Sort-Object Name
	foreach ($module in $modules) {
		$dir = $module.FullName
		$head = (& git -C $dir rev-parse HEAD 2>$null)
		if (-not $head) { $head = 'sem-commit' }
		# alterações locais: o diff dos arquivos rastreados e o conteúdo dos não rastreados (target/ fica no .gitignore)
		$diff = (& git -C $dir diff HEAD --no-color 2>$null) -join "`n"
		$untracked = @(& git -C $dir ls-files --others --exclude-standard 2>$null)
		$untrackedHashes = @(foreach ($file in $untracked) {
			$path = Join-Path $dir $file
			if (Test-Path $path -PathType Leaf) { "$file " + (& git -C $dir hash-object -- $file 2>$null) }
		}) -join "`n"
		$local = if ($diff -or $untrackedHashes) { Get-TextHash ($diff + "`n--`n" + $untrackedHashes) } else { 'limpo' }
		$lines.Add("$($module.Name)`t$head`t$local")
	}
	return ($lines -join "`n")
}

# os módulos cuja linha mudou entre duas impressões digitais (para o log dizer o que motivou a rodada)
function Compare-CodeFingerprint([string]$Previous, [string]$Current) {
	$before = @{}
	foreach ($line in ($Previous -split "`n")) { $cols = $line -split "`t"; if ($cols.Count -ge 3) { $before[$cols[0]] = $line } }
	$changed = foreach ($line in ($Current -split "`n")) {
		$cols = $line -split "`t"
		if ($cols.Count -ge 3 -and $before[$cols[0]] -ne $line) { $cols[0] }
	}
	return @($changed)
}
