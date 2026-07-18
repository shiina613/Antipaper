param(
    [string]$OutputPath = ".artifacts\antipaper-backend.zip"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$resolvedOutput = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputPath))
$artifactRoot = Split-Path -Parent $resolvedOutput
New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null

$tempRoot = Join-Path $env:TEMP "antipaper-backend-package"
if (Test-Path $tempRoot) {
    Remove-Item -Recurse -Force $tempRoot
}

New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

$itemsToCopy = @(
    "backend",
    "src",
    "scripts\run_backend.ps1",
    "requirements.txt",
    "backend\requirements.txt",
    ".env.example",
    "README.md"
)

foreach ($item in $itemsToCopy) {
    $source = Join-Path $repoRoot $item
    if (-not (Test-Path $source)) {
        continue
    }

    $destination = Join-Path $tempRoot $item
    $destinationParent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
    Copy-Item -Recurse -Force -Path $source -Destination $destination
}

if (Test-Path $resolvedOutput) {
    Remove-Item -Force $resolvedOutput
}

Compress-Archive -Path (Join-Path $tempRoot "*") -DestinationPath $resolvedOutput -Force
Write-Host "Created backend package: $resolvedOutput"
