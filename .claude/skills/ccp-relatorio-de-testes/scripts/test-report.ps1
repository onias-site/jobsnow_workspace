<#
Relatorio de testes do workspace: inventario estatico (o que o Surefire executaria) e,
quando houver, o resultado da ultima execucao lido de target/surefire-reports.
#>
param(
	[string]$Root = "C:\eclipse-workspaces\ccp",
	[string]$Module = "ccp_rest-api-tests_jobsnow",
	[string]$Package = "",
	[int]$Top = 15,
	[switch]$AllPackages,
	[switch]$NoReports,
	[string]$FailedNames = ""
)

$ErrorActionPreference = "Stop"

$moduleDir = Join-Path $Root $Module
$testRoot = Join-Path $moduleDir "src\test\java"
$pomPath = Join-Path $moduleDir "pom.xml"

if (-not (Test-Path $testRoot)) { throw "Nao encontrei $testRoot" }
if (-not (Test-Path $pomPath)) { throw "Nao encontrei $pomPath" }

function Convert-AntPatternToRegex {
	param([string]$pattern)
	$escaped = [regex]::Escape($pattern)
	$escaped = $escaped -replace '\\\*\\\*/', '(.*/)?'
	$escaped = $escaped -replace '\\\*\\\*', '.*'
	$escaped = $escaped -replace '\\\*', '[^/]*'
	return ('^' + $escaped + '$')
}

function Sum-Prop {
	param($items, [string]$prop)
	$total = 0
	foreach ($i in $items) { $total = $total + $i.$prop }
	return $total
}

$pom = Get-Content $pomPath -Raw
$surefireMatch = [regex]::Match($pom, '<artifactId>maven-surefire-plugin</artifactId>[\s\S]*?</plugin>')
if (-not $surefireMatch.Success) { throw "Bloco do maven-surefire-plugin nao encontrado em $pomPath" }
$block = $surefireMatch.Value

$includePatterns = @()
foreach ($m in [regex]::Matches($block, '<include>([^<]+)</include>')) {
	$includePatterns = $includePatterns + $m.Groups[1].Value.Trim()
}
$excludePatterns = @()
foreach ($m in [regex]::Matches($block, '<exclude>([^<]+)</exclude>')) {
	$excludePatterns = $excludePatterns + $m.Groups[1].Value.Trim()
}
if ($includePatterns.Count -eq 0) {
	$includePatterns = @("**/Test*.java", "**/*Test.java", "**/*Tests.java", "**/*TestCase.java")
}

$includeRegex = @()
foreach ($p in $includePatterns) { $includeRegex = $includeRegex + (Convert-AntPatternToRegex $p) }
$excludeRegex = @()
foreach ($p in $excludePatterns) { $excludeRegex = $excludeRegex + (Convert-AntPatternToRegex $p) }

$files = Get-ChildItem -Path $testRoot -Recurse -Filter *.java -File
$rows = @()

foreach ($f in $files) {
	$rel = $f.FullName.Substring($testRoot.Length + 1).Replace('\', '/')

	$isIncluded = $false
	foreach ($rx in $includeRegex) {
		if ($rel -match $rx) { $isIncluded = $true; break }
	}
	if ($isIncluded) {
		foreach ($rx in $excludeRegex) {
			if ($rel -match $rx) { $isIncluded = $false; break }
		}
	}

	$raw = Get-Content $f.FullName -Raw
	if ($null -eq $raw) { $raw = "" }
	$clean = [regex]::Replace($raw, '/\*[\s\S]*?\*/', '')
	$clean = [regex]::Replace($clean, '//[^\r\n]*', '')

	$pkg = ""
	if ($rel.Contains('/')) {
		$pkg = $rel.Substring(0, $rel.LastIndexOf('/')).Replace('/', '.')
	}

	$row = New-Object psobject
	Add-Member -InputObject $row -MemberType NoteProperty -Name Path -Value $rel
	Add-Member -InputObject $row -MemberType NoteProperty -Name Package -Value $pkg
	Add-Member -InputObject $row -MemberType NoteProperty -Name Included -Value $isIncluded
	$testsClean = ([regex]::Matches($clean, '@Test\b')).Count
	$testsRaw = ([regex]::Matches($raw, '@Test\b')).Count
	Add-Member -InputObject $row -MemberType NoteProperty -Name Tests -Value $testsClean
	Add-Member -InputObject $row -MemberType NoteProperty -Name Commented -Value ($testsRaw - $testsClean)
	Add-Member -InputObject $row -MemberType NoteProperty -Name Expected -Value ([regex]::Matches($clean, '@Test\s*\(\s*expected')).Count
	Add-Member -InputObject $row -MemberType NoteProperty -Name Ignored -Value ([regex]::Matches($clean, '@Ignore\b')).Count
	Add-Member -InputObject $row -MemberType NoteProperty -Name RunWith -Value ([regex]::Matches($clean, '@RunWith\b')).Count
	Add-Member -InputObject $row -MemberType NoteProperty -Name Abstract -Value ([regex]::IsMatch($clean, 'abstract\s+class'))
	$rows = $rows + $row
}

if ($Package -ne "") {
	$needle = $Package.Replace('/', '.')
	$rows = @($rows | Where-Object { $_.Package.StartsWith($needle) })
}

$included = @($rows | Where-Object { $_.Included })
$notIncluded = @($rows | Where-Object { -not $_.Included })
$testClasses = @($included | Where-Object { $_.Tests -gt 0 })
$testClasses = @($testClasses | Where-Object { -not $_.Abstract })
$orphans = @($notIncluded | Where-Object { $_.Tests -gt 0 })
$abstractWithTests = @($included | Where-Object { $_.Tests -gt 0 })
$abstractWithTests = @($abstractWithTests | Where-Object { $_.Abstract })
$support = @($rows | Where-Object { $_.Tests -eq 0 })
$support = @($support | Where-Object { $_.Commented -eq 0 })
$commented = @($rows | Where-Object { $_.Commented -gt 0 })

$totalTests = Sum-Prop $testClasses 'Tests'
$totalExpected = Sum-Prop $testClasses 'Expected'
$totalIgnored = Sum-Prop $rows 'Ignored'
$totalRunWith = Sum-Prop $rows 'RunWith'

Write-Output "=== INVENTARIO ESTATICO ==="
Write-Output ("modulo ...................... {0}" -f $Module)
if ($Package -ne "") { Write-Output ("filtro de pacote ............ {0}" -f $Package) }
Write-Output ("arquivos .java em src/test .. {0}" -f $rows.Count)
Write-Output ("classes de teste ............ {0}" -f $testClasses.Count)
Write-Output ("metodos @Test ............... {0}" -f $totalTests)
Write-Output ("  dos quais @Test(expected) . {0}" -f $totalExpected)
Write-Output ("@Ignore ..................... {0}" -f $totalIgnored)
Write-Output ("@RunWith .................... {0}" -f $totalRunWith)
Write-Output ("desativados por comentario .. {0}" -f (Sum-Prop $rows 'Commented'))
Write-Output ("arquivos de apoio (sem @Test) {0}" -f $support.Count)

if ($commented.Count -gt 0) {
	Write-Output ""
	Write-Output "Testes desativados por comentario (//@Test) - nao aparecem como skipped em relatorio nenhum:"
	foreach ($c in @($commented | Sort-Object -Property Commented -Descending)) {
		Write-Output ("  {0,4}  {1}" -f $c.Commented, $c.Path)
	}
}

if ($orphans.Count -gt 0) {
	Write-Output ""
	Write-Output "!! TESTES ORFAOS: tem @Test mas os includes do pom nao os alcancam - nunca rodam !!"
	foreach ($o in @($orphans | Sort-Object -Property Tests -Descending)) {
		Write-Output ("  {0,4}  {1}" -f $o.Tests, $o.Path)
	}
}

if ($abstractWithTests.Count -gt 0) {
	Write-Output ""
	Write-Output "Classes abstratas com @Test (contam pelas filhas, nao por si):"
	foreach ($a in $abstractWithTests) {
		Write-Output ("  {0,4}  {1}" -f $a.Tests, $a.Path)
	}
}

Write-Output ""
Write-Output "=== @Test POR PACOTE ==="
$grouped = $testClasses | Group-Object -Property Package
$byPackage = @()
foreach ($g in $grouped) {
	$item = New-Object psobject
	Add-Member -InputObject $item -MemberType NoteProperty -Name Package -Value $g.Name
	Add-Member -InputObject $item -MemberType NoteProperty -Name Classes -Value $g.Count
	Add-Member -InputObject $item -MemberType NoteProperty -Name Tests -Value (Sum-Prop $g.Group 'Tests')
	$byPackage = $byPackage + $item
}
$byPackage = @($byPackage | Sort-Object -Property Tests -Descending)

$shown = $byPackage
if (-not $AllPackages) { $shown = @($byPackage | Select-Object -First $Top) }
foreach ($p in $shown) {
	Write-Output ("{0,5} testes  {1,3} classes  {2}" -f $p.Tests, $p.Classes, $p.Package)
}
if (-not $AllPackages) {
	if ($byPackage.Count -gt $Top) {
		Write-Output ("... e mais {0} pacotes (use -AllPackages)" -f ($byPackage.Count - $Top))
	}
}

if ($NoReports) { return }

$reportsDir = Join-Path $moduleDir "target\surefire-reports"
Write-Output ""
Write-Output "=== ULTIMA EXECUCAO (target\surefire-reports) ==="

if (-not (Test-Path $reportsDir)) {
	Write-Output "Nenhum surefire-report encontrado. Rode os testes antes para ter resultado."
	return
}

$xmls = @(Get-ChildItem -Path $reportsDir -Filter "TEST-*.xml" -File)
if ($xmls.Count -eq 0) {
	Write-Output "Nenhum TEST-*.xml em $reportsDir."
	return
}

$suites = @()
$failedTests = @()
$needleSuite = ""
if ($Package -ne "") { $needleSuite = $Package.Replace('/', '.') }

foreach ($x in $xmls) {
	$doc = $null
	try { $doc = [xml](Get-Content $x.FullName -Raw) } catch { continue }
	if ($null -eq $doc) { continue }
	$ts = $doc.testsuite
	if ($null -eq $ts) { continue }

	$suiteName = [string]$ts.name
	if ($needleSuite -ne "") {
		if (-not $suiteName.StartsWith($needleSuite)) { continue }
	}

	$t = 0; $e = 0; $fl = 0; $s = 0
	[void][int]::TryParse([string]$ts.tests, [ref]$t)
	[void][int]::TryParse([string]$ts.errors, [ref]$e)
	[void][int]::TryParse([string]$ts.failures, [ref]$fl)
	[void][int]::TryParse([string]$ts.skipped, [ref]$s)

	$suite = New-Object psobject
	Add-Member -InputObject $suite -MemberType NoteProperty -Name Suite -Value $suiteName
	Add-Member -InputObject $suite -MemberType NoteProperty -Name Tests -Value $t
	Add-Member -InputObject $suite -MemberType NoteProperty -Name Errors -Value $e
	Add-Member -InputObject $suite -MemberType NoteProperty -Name Failures -Value $fl
	Add-Member -InputObject $suite -MemberType NoteProperty -Name Skipped -Value $s
	Add-Member -InputObject $suite -MemberType NoteProperty -Name When -Value $x.LastWriteTime
	Add-Member -InputObject $suite -MemberType NoteProperty -Name Broken -Value ($e + $fl)
	$suites = $suites + $suite

	foreach ($tc in @($ts.testcase)) {
		if ($null -eq $tc) { continue }
		$broke = $false
		if ($null -ne $tc.error) { $broke = $true }
		if ($null -ne $tc.failure) { $broke = $true }
		if ($broke) { $failedTests = $failedTests + ("{0}.{1}" -f $suiteName, [string]$tc.name) }
	}
}

if ($suites.Count -eq 0) {
	Write-Output "Nenhuma suite corresponde ao filtro."
	return
}

$ordered = @($suites | Sort-Object -Property When)
$first = $ordered[0].When
$last = $ordered[$ordered.Count - 1].When
$executed = Sum-Prop $suites 'Tests'

Write-Output ("reports gravados entre .. {0}  e  {1}" -f $first, $last)
Write-Output ("classes ................. {0}" -f $suites.Count)
Write-Output ("testes executados ....... {0}" -f $executed)
Write-Output ("errors .................. {0}" -f (Sum-Prop $suites 'Errors'))
Write-Output ("failures ................ {0}" -f (Sum-Prop $suites 'Failures'))
Write-Output ("skipped ................. {0}" -f (Sum-Prop $suites 'Skipped'))
if ($totalTests -gt 0) {
	Write-Output ("cobertura ............... {0} de {1} metodos @Test aparecem nestes reports" -f $executed, $totalTests)
}

$broken = @($suites | Where-Object { $_.Broken -gt 0 })
$broken = @($broken | Sort-Object -Property Broken -Descending)
if ($broken.Count -gt 0) {
	Write-Output ""
	Write-Output "Classes com erro/falha:"
	foreach ($b in $broken) {
		Write-Output ("  {0,3} de {1,3}  {2}" -f $b.Broken, $b.Tests, $b.Suite)
	}
}

if ($failedTests.Count -gt 0) {
	Write-Output ""
	Write-Output ("Testes com erro/falha ({0}), por nome:" -f $failedTests.Count)
	foreach ($n in @($failedTests | Sort-Object)) {
		Write-Output ("  {0}" -f $n)
	}
}

if ($FailedNames -ne "") {
	$failedTests | Sort-Object | Set-Content -Path $FailedNames -Encoding utf8
	Write-Output ""
	Write-Output ("Nomes gravados em {0} - compare com a proxima execucao via Compare-Object." -f $FailedNames)
}
