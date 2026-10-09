param(
	[string]$Root = 'C:\eclipse-workspaces\ccp',
	[string]$Module = 'ccp_rest-api-tests_jobsnow',
	[string]$Test = '',
	[string]$OutDir = (Join-Path $env:TEMP 'ccp-coverage'),
	[switch]$SkipRun,
	[switch]$NoApi,
	[switch]$IncludeTestModule,
	[string]$ApiModule = 'jn_rest-api_spring_jobsnow_dependency-chooser',
	[string]$ApiMainClass = 'com.jn.rest.api.JnRestApiSpringStarter',
	[int]$AgentPort = 6300,
	[string]$Java = 'C:\Program Files\Java\jdk-17\bin\java.exe',
	[string]$JacocoVersion = '0.8.12',
	[string]$AsmVersion = '9.7',
	[string]$HistoryFile = (Join-Path (Split-Path $PSScriptRoot -Parent) 'history\coverage-projects.tsv')
)

# Coverage report of the workspace: starts the jn API (port 8080) with a JaCoCo agent in tcpserver mode, runs the
# tests of $Module with another agent attached to the Surefire JVM, dumps the API's data, stops the API, and then
# analyzes both .exec files together against target/classes of every module. Writes coverage-report.html
# (collapsible, EclEmma layout) and coverage.tsv (one line per file) into $OutDir.

$ErrorActionPreference = 'Stop'

if ($OutDir -match ' ') {
	throw "OutDir must not contain spaces (the -javaagent argument breaks): $OutDir"
}
New-Item -ItemType Directory -Force $OutDir | Out-Null

$m2 = Join-Path $env:USERPROFILE '.m2\repository'
$jars = [ordered]@{
	agent  = "$m2\org\jacoco\org.jacoco.agent\$JacocoVersion\org.jacoco.agent-$JacocoVersion-runtime.jar"
	core   = "$m2\org\jacoco\org.jacoco.core\$JacocoVersion\org.jacoco.core-$JacocoVersion.jar"
	asm    = "$m2\org\ow2\asm\asm\$AsmVersion\asm-$AsmVersion.jar"
	commons= "$m2\org\ow2\asm\asm-commons\$AsmVersion\asm-commons-$AsmVersion.jar"
	tree   = "$m2\org\ow2\asm\asm-tree\$AsmVersion\asm-tree-$AsmVersion.jar"
}
foreach ($k in $jars.Keys) {
	if (-not (Test-Path $jars[$k])) {
		throw "Missing $k jar: $($jars[$k]). Fetch it with: mvn dependency:get -Dartifact=org.jacoco:org.jacoco.agent:${JacocoVersion}:jar:runtime (or the matching core/asm artifact)"
	}
}

# the agent path goes inside -DargLine: copy it to a folder without spaces
$agent = Join-Path $OutDir 'jacocoagent.jar'
Copy-Item $jars.agent $agent -Force
$exec = Join-Path $OutDir 'jacoco.exec'
$apiExec = Join-Path $OutDir 'jacoco-api.exec'
$includes = 'includes=com.ccp.*:com.jn.*:com.jb.*:com.vis.*'
$apiClasses = Join-Path $OutDir 'api-classes'
$testsFile = Join-Path $OutDir 'tests-run.txt'

$classes = Join-Path $OutDir 'classes'
New-Item -ItemType Directory -Force $classes | Out-Null
$cp = @($jars.core, $jars.asm, $jars.commons, $jars.tree) -join ';'
& javac -nowarn -cp $cp -d $classes (Join-Path $PSScriptRoot 'CoverageReport.java') (Join-Path $PSScriptRoot 'AgentDump.java')
if ($LASTEXITCODE -ne 0) { throw 'javac failed' }

function Test-Port([int]$port) {
	$client = New-Object Net.Sockets.TcpClient
	try { return $client.ConnectAsync('localhost', $port).Wait(1000) -and $client.Connected } catch { return $false } finally { $client.Dispose() }
}

# Maven writes warnings to stderr (SLF4J, for instance); under 'Stop' PowerShell 5.1 turns them into terminating errors
function Invoke-Maven([string[]]$mvnArgs, [string]$where) {
	Push-Location $where
	$ErrorActionPreference = 'Continue'
	try { & mvn @mvnArgs 2>&1 | ForEach-Object { "$_" } }
	finally { Pop-Location }
}

# runs are compared only with runs of the same scope: a filtered run measures less code than the full suite
$runScope = if ($Test) { "test=$Test" } else { 'full' }
if ($IncludeTestModule) { $runScope += '+test-module' }
$previousTsv = Join-Path $OutDir 'coverage.tsv'

# the history keeps the project totals of every run, so the next run can be compared with this one; a run made
# before the history existed is imported from the coverage.tsv it left behind, as long as it is still there
function Import-PreviousRun {
	if ($HistoryFile -eq '-' -or -not (Test-Path $previousTsv)) { return }
	$label = (Get-Item $previousTsv).LastWriteTime.ToString('yyyy-MM-dd HH:mm')
	if ((Test-Path $HistoryFile) -and (Select-String -Path $HistoryFile -SimpleMatch "$label`t" -Quiet)) { return }
	$tests = if (Test-Path $testsFile) { (Get-Content $testsFile -Raw).Trim() } else { '' }
	$lines = New-Object System.Collections.Generic.List[string]
	if (-not (Test-Path $HistoryFile)) {
		New-Item -ItemType Directory -Force (Split-Path $HistoryFile -Parent) | Out-Null
		$lines.Add("run`tscope`ttests`tproject`tcovered`tmissed")
	}
	# the scope of an imported run is unknown; it is taken as the scope of this run
	Import-Csv -Path $previousTsv -Delimiter "`t" | Group-Object project | ForEach-Object {
		$covered = ($_.Group | Measure-Object -Property covered -Sum).Sum
		$missed = ($_.Group | Measure-Object -Property missed -Sum).Sum
		$lines.Add("$label`t$runScope`t$tests`t$($_.Name)`t$covered`t$missed")
	}
	[IO.File]::AppendAllLines($HistoryFile, $lines, (New-Object Text.UTF8Encoding $false))
	Write-Host "Imported the run of $label into $HistoryFile"
}

$apiProcess = $null
$apiMeasured = $false
if (-not $SkipRun) {
	Import-PreviousRun
	if (Test-Path $exec) { Remove-Item $exec -Force -Confirm:$false }
	if (Test-Path $apiExec) { Remove-Item $apiExec -Force -Confirm:$false }

	if (-not $NoApi) {
		if (Test-Port 8080) {
			Write-Warning 'Port 8080 is already taken (the API in Eclipse?): the tests use it, but the code run inside it is not measured. Stop it to measure the API too.'
		} else {
			$apiDir = Join-Path $Root $ApiModule
			$cpFile = Join-Path $OutDir 'api-classpath.txt'
			Write-Host "Building the classpath of $ApiModule"
			Invoke-Maven @('-o', '-q', 'compile', 'dependency:build-classpath', "-Dmdep.outputFile=$cpFile") $apiDir | Select-Object -Last 5
			# the API runs from a snapshot of target/classes: Eclipse may rewrite target/classes during the run, and
			# the report must analyze exactly the bytecode that ran
			if (Test-Path $apiClasses) { Remove-Item $apiClasses -Recurse -Force -Confirm:$false }
			Copy-Item (Join-Path $apiDir 'target\classes') $apiClasses -Recurse
			$apiClasspath = $apiClasses + ';' + (Get-Content $cpFile -Raw).Trim()
			# DevTools restarts the API whenever its classpath changes, and port 8080 goes down meanwhile: on
			# 2026-10-02 an Eclipse rebuild restarted it mid-run and 3 REST tests got "connection refused"
			$apiArgs = "-javaagent:$agent=output=tcpserver,address=127.0.0.1,port=$AgentPort,$includes -Dspring.devtools.restart.enabled=false -cp `"$apiClasspath`" $ApiMainClass"
			$apiLog = Join-Path $OutDir 'api.log'
			$apiProcess = Start-Process -FilePath $Java -ArgumentList $apiArgs -WorkingDirectory $apiDir -RedirectStandardOutput $apiLog -RedirectStandardError (Join-Path $OutDir 'api-err.log') -WindowStyle Hidden -PassThru
			$deadline = (Get-Date).AddSeconds(120)
			while (-not (Test-Port 8080)) {
				if ($apiProcess.HasExited) { throw "The API exited during startup, see $apiLog" }
				if ((Get-Date) -gt $deadline) { Stop-Process -Id $apiProcess.Id -Force -Confirm:$false; throw "The API did not open port 8080 in 120 s, see $apiLog" }
				Start-Sleep -Milliseconds 500
			}
			Write-Host "API up (PID $($apiProcess.Id)), agent listening on port $AgentPort"
		}
	} elseif (-not (Test-Port 8080)) {
		Write-Warning 'Nothing listens on localhost:8080: the com.jn.rest.api.* tests will fail with connection refused (about 62 of them).'
	}

	try {
		$argLine = "-DargLine=-javaagent:$agent=destfile=$exec,$includes"
		$mvnArgs = @('-o', 'test', '-fn', '-pl', $Module, $argLine)
		if ($Test) { $mvnArgs += @("-Dtest=$Test", '-Dsurefire.failIfNoSpecifiedTests=false') }
		Write-Host "Running: mvn $($mvnArgs -join ' ')"
		$mvnLines = @(Invoke-Maven $mvnArgs $Root | Select-String -Pattern 'Tests run:|BUILD|<<< (FAILURE|ERROR)' | ForEach-Object { $_.Line })
		$mvnLines | Select-Object -Last 40
		# the overall Surefire summary is the last "Tests run" line without "-- in <class>"
		$summary = $mvnLines | Where-Object { $_ -match 'Tests run: \d+, Failures: \d+, Errors: \d+, Skipped: \d+\s*$' } | Select-Object -Last 1
		if ($summary -and $summary -match 'Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)') {
			$run = [int]$Matches[1]; $failures = [int]$Matches[2]; $errors = [int]$Matches[3]; $skipped = [int]$Matches[4]
			$passed = $run - $failures - $errors - $skipped
			"$run (passed: $passed, failures: $failures, errors: $errors, skipped: $skipped)" | Set-Content -Path $testsFile -Encoding ASCII
		} elseif (Test-Path $testsFile) {
			Remove-Item $testsFile -Force -Confirm:$false
		}
	}
	finally {
		if ($apiProcess) {
			# the API is stopped by force, so its agent never writes on exit: ask for the data first
			& java -cp "$classes;$cp" AgentDump $AgentPort $apiExec
			$apiMeasured = ($LASTEXITCODE -eq 0) -and (Test-Path $apiExec)
			if (-not $apiMeasured) { Write-Warning 'Could not dump the API coverage' }
			Stop-Process -Id $apiProcess.Id -Force -Confirm:$false
			Write-Host "API stopped (PID $($apiProcess.Id))"
		}
	}
} else {
	$apiMeasured = Test-Path $apiExec
}
if (-not (Test-Path $exec)) { throw "No jacoco.exec at $exec (run without -SkipRun first)" }
# an exec with only the header means the tests never ran (a Surefire fork that died while scanning, for instance)
if ((Get-Item $exec).Length -lt 1024) {
	throw "The tests did not run: $exec has only $((Get-Item $exec).Length) bytes. See the latest *.dump in $Root\$Module\target\surefire-reports (with Eclipse open, a ClassNotFoundException of a test class means Eclipse was rebuilding target; run again)."
}

$execFiles = if ($apiMeasured) { "$exec;$apiExec" } else { $exec }
$scope = if ($Test) { "tests of $Module matching '$Test'" } else { "full test suite of $Module" }
if (-not $IncludeTestModule) { $scope += " (the $Module project itself left out)" }
$apiScope = if ($apiMeasured) { ' plus the code run inside the jn API' } else { '' }
$execDate = (Get-Item $exec).LastWriteTime.ToString('yyyy-MM-dd HH:mm')
$subtitle = "JaCoCo $JacocoVersion engine (the one EclEmma uses), instruction counters, $scope$apiScope, run on $execDate."
$html = Join-Path $OutDir 'coverage-report.html'
$tsv = Join-Path $OutDir 'coverage.tsv'
# the business modules are analyzed from their jars in the local repository (what the tests JVM loaded), the API
# from the snapshot it ran from; target/classes only as the last resort, because Eclipse rewrites it
# '-' stands for "none": Windows PowerShell drops empty-string arguments when calling a native program, which
# shifted the next arguments and silently put the tests module back in the report (seen on 2026-10-04)
$overrides = if ($apiMeasured -and (Test-Path $apiClasses)) { "$ApiModule=$apiClasses" } else { '-' }
# the src/main of the tests module is support code for the tests (fixtures, templates, http helpers), not
# production code: it is left out unless asked, so the percentage measures only what the tests exercise
$excluded = if ($IncludeTestModule) { '-' } else { $Module }
$testsRun = if (Test-Path $testsFile) { (Get-Content $testsFile -Raw).Trim() } else { '' }
if (-not $testsRun) { Write-Warning 'The number of tests run is unknown (no Surefire summary in this run)' }
if (-not $testsRun) { $testsRun = '-' }
& java -cp "$classes;$cp" CoverageReport $execFiles $Root $html $tsv $subtitle $m2 $overrides $excluded $testsRun $HistoryFile $execDate $runScope
if ($LASTEXITCODE -ne 0) { throw 'CoverageReport failed' }

Write-Host ""
Write-Host "HTML:    $html"
Write-Host "TSV:     $tsv"
Write-Host "HISTORY: $HistoryFile"
