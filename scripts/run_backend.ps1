param(
    [Alias("Host")]
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$pythonCandidates = @(
    (Join-Path $repoRoot ".venv\Scripts\python.exe"),
    (Join-Path $repoRoot "backend\.venv\Scripts\python.exe")
)

$pythonCommand = $null
foreach ($candidate in $pythonCandidates) {
    if (Test-Path $candidate) {
        $pythonCommand = $candidate
        break
    }
}

if ($null -eq $pythonCommand) {
    $pythonAlias = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $pythonAlias) {
        $pythonCommand = $pythonAlias.Source
    }
}

if ($null -eq $pythonCommand) {
    $pyAlias = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pyAlias) {
        $pythonCommand = $pyAlias.Source
    }
}

if ($null -eq $pythonCommand) {
    throw "Could not find a Python runtime. Create .venv or install Python."
}

$backendArgs = @("-m", "backend", "--host", $BindHost, "--port", $Port)
if ($Reload) {
    $backendArgs += "--reload"
}

& $pythonCommand @backendArgs
