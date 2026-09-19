<#
.SYNOPSIS
    Operation Silent Ridge — one-command local launcher (E02).

.DESCRIPTION
    Thin wrapper over `python -m ridge.deploy`. Checks the supported host
    prerequisites, validates that a deployment profile is present, and invokes
    the shared CLI with correct quoting and exit-code passthrough.

    Secrets are never accepted as command-line arguments; they live only in
    the private runtime directory. `prepare` verifies prerequisites and cached
    images only — it performs no installs, no pulls and no reboots, and makes
    zero outbound network calls.

.EXAMPLE
    .\ridge.ps1 prepare -Profile .\work\n4-run\profile.json -Runtime .\work\n4-run
    .\ridge.ps1 up      -Profile .\work\n4-run\profile.json -Runtime .\work\n4-run
    .\ridge.ps1 status  -Profile .\work\n4-run\profile.json -Runtime .\work\n4-run
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('prepare', 'doctor', 'build', 'verify-build', 'up', 'status',
                 'start', 'pause', 'backup', 'restore', 'switch', 'down')]
    [string]$Action,

    [Parameter(Position = 1)]
    [string]$Profile,

    [string]$Runtime,

    [string]$Operator = 'deploy',

    [string]$Python = 'python'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
if (-not $scriptDir) { $scriptDir = (Get-Location).Path }
if (-not $Runtime) { $Runtime = Join-Path $scriptDir 'work\deploy-runtime' }

function Fail([string]$Message, [int]$Code = 2) {
    Write-Host "ridge: $Message" -ForegroundColor Red
    exit $Code
}

$root = $scriptDir
if (-not (Test-Path (Join-Path $root 'ridge\deploy\__main__.py'))) {
    Fail "cannot locate the repository root from $scriptDir"
}

# --- prerequisite checks (no installs, no outbound calls) -------------------
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Fail "PowerShell 5 or newer is required (found $($PSVersionTable.PSVersion))"
}
$pythonCmd = Get-Command $Python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Fail "Python is not on PATH as '$Python'. Install the pinned interpreter from the offline media, then rerun prepare."
}
try {
    $null = & $Python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>&1
    if ($LASTEXITCODE -ne 0) { Fail "Python 3.11 or newer is required" }
} catch {
    Fail "could not execute $Python`: $_"
}

$dockerCmd = Get-Command 'docker' -ErrorAction SilentlyContinue
$dockerDesktopBin = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin'
if (-not $dockerCmd -and (Test-Path (Join-Path $dockerDesktopBin 'docker.exe'))) {
    $env:PATH = "$env:PATH;$dockerDesktopBin"
    $dockerCmd = Get-Command 'docker' -ErrorAction SilentlyContinue
}
if (-not $dockerCmd) {
    Fail "Docker CLI not found. Start Docker Desktop once and log in, then rerun prepare."
}
& docker info 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
    Fail "the Docker engine is not reachable. Start Docker Desktop, wait for it to report running, then rerun prepare."
}

# --- action dispatch ---------------------------------------------------------
$lifecycle = @('up', 'status', 'start', 'pause', 'backup', 'restore', 'switch', 'down')

if ($Action -eq 'prepare') {
    Write-Host "ridge: prerequisites OK (PowerShell $($PSVersionTable.PSVersion), $($pythonCmd.Source), Docker engine reachable)"
    if ($Profile) {
        if (-not (Test-Path $Profile)) { Fail "profile not found: $Profile" }
        Write-Host "ridge: profile present: $Profile"
    }
    # Cached-image check is offline: docker image inspect never pulls.
    $missing = @()
    foreach ($component in 'iris', 'ctfd', 'integration', 'desktop') {
        & docker image inspect "silent-ridge-${component}:dev" 1>$null 2>$null
        if ($LASTEXITCODE -ne 0) { $missing += $component }
    }
    if ($missing.Count -gt 0) {
        Write-Host "ridge: images not yet built: $($missing -join ', ')"
        Write-Host "ridge: build them with:  $Python -m ridge.deploy build   (requires the release media; run once, never on event day)"
        exit 1
    }
    Write-Host "ridge: all four component images are cached locally; prepare makes zero outbound calls"
    exit 0
}

Push-Location $root
try {
    if ($Action -in @('doctor', 'build', 'verify-build')) {
        & $Python -m ridge.deploy $Action
        exit $LASTEXITCODE
    }
    if ($Action -in $lifecycle) {
        if (-not $Profile) { Fail "-Profile is required for $Action" }
        if (-not (Test-Path $Profile)) { Fail "profile not found: $Profile" }
        & $Python -m ridge.deploy $Action --profile $Profile --runtime $Runtime --operator $Operator
        exit $LASTEXITCODE
    }
    Fail "unhandled action $Action"
} finally {
    Pop-Location
}
