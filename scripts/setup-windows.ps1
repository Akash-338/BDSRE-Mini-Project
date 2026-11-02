param(
    [string]$ProjectRoot = (Get-Location).Path,
    [string]$ToolsRoot = (Join-Path (Get-Location).Path '.tools'),
    [switch]$SkipSpark
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$ToolsRoot = [System.IO.Path]::GetFullPath($ToolsRoot)
$pythonCommand = Get-Command python -ErrorAction Stop
$python = $pythonCommand.Source
if (-not $python) { $python = $pythonCommand.Definition }
$javaCommand = Get-Command java -ErrorAction Stop
$javaPath = $javaCommand.Source
if (-not $javaPath) { $javaPath = $javaCommand.Definition }
$javaPath = (Resolve-Path -LiteralPath $javaPath).Path
$javaHome = Split-Path (Split-Path $javaPath -Parent) -Parent
$version = & $python -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sep=chr(46))'
if ($version -ne '3.12') { throw "Python 3.12 is required; found $version at $python" }
$previousErrorActionPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    $javaVersionOutput = & $javaPath -version 2>&1
    $javaExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousErrorActionPreference
}
if ($javaExitCode -ne 0) { throw "Could not determine Java version from $javaPath (exit code $javaExitCode)" }
$javaVersion = ($javaVersionOutput | Where-Object { $_ -match 'version "17\.' } | Select-Object -First 1) -join ''
if ($javaVersion -notmatch '17\.') { throw "Java 17 is required; found $javaVersion at $javaPath" }
$venv = Join-Path $ToolsRoot 'venv'
$cache = Join-Path $ToolsRoot 'cache'
$temp = Join-Path $ToolsRoot 'temp'
New-Item -ItemType Directory -Force -Path $ToolsRoot,$cache,$temp | Out-Null
if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) {
    & $python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create virtual environment.' }
}
$env:TEMP=$temp
$env:TMP=$temp
$env:PIP_CACHE_DIR=Join-Path $cache 'pip'
$env:BDSRE_TOOLS_ROOT=$ToolsRoot
$venvPython=Join-Path $venv 'Scripts\python.exe'
& $venvPython -m pip install -r (Join-Path $ProjectRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $venvPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed.' }
if (-not $SkipSpark) {
    $env:JAVA_HOME=$javaHome
    $env:PATH="$(Join-Path $venv 'Scripts');$(Join-Path $javaHome 'bin');$env:PATH"
    $env:JAVA_TOOL_OPTIONS="-Duser.home=$(Join-Path $ToolsRoot 'java-home') -Djava.io.tmpdir=$temp"
    $env:PYSPARK_PYTHON=$venvPython
    $env:SPARK_LOCAL_DIRS=$temp
    $env:JUPYTER_CONFIG_DIR=Join-Path $ToolsRoot 'jupyter\config'
    $env:JUPYTER_DATA_DIR=Join-Path $ToolsRoot 'jupyter\data'
    $env:JUPYTER_RUNTIME_DIR=Join-Path $ToolsRoot 'jupyter\runtime'
    $env:MPLCONFIGDIR=Join-Path $cache 'matplotlib'
    $env:PYTHONPYCACHEPREFIX=Join-Path $cache 'pycache'
}
Write-Host "Setup complete. Activate with: $venv\Scripts\Activate.ps1"
Write-Host "Run smoke test with: & '$venvPython' '$(Join-Path $ProjectRoot 'scripts\smoke_test.py')'"
Write-Host "Tools, virtualenv, and caches are under: $ToolsRoot"


