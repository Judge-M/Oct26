# E02 - thin Windows launcher for the shared deployment CLI.
# Checks prerequisites, validates the profile, then invokes `python -m ridge.deploy`.
# It does not duplicate deployment logic and never accepts secrets on the command line.
[CmdletBinding(PositionalBinding = $false)]
param(
    [ValidateSet('prepare', 'up', 'status', 'start', 'pause', 'backup', 'restore', 'down')]
    [string]$Action = 'status',
    [string]$Event,
    [string]$Profile,
    [string]$Release,
    [string]$Work,
    [string]$Provider,
    [string]$Destination,
    [switch]$Start,
    [switch]$CheckOnly,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Extra = @()
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Write-Fail([string]$Message) {
    Write-Host ("ridge: " + $Message) -ForegroundColor Red
    exit 2
}

foreach ($token in $Extra) {
    if ($token -match '(?i)(password|secret|token|api[_-]?key)\s*=') {
        Write-Fail 'Do not pass secrets on the command line; put them in a private profile file.'
    }
}
foreach ($name in 'RIDGE_PASSWORD', 'RIDGE_SECRET', 'RIDGE_TOKEN') {
    if (Test-Path ("Env:" + $name)) {
        Write-Fail ("Remove " + $name + " from the environment; secrets belong in a private file.")
    }
}

$psVersion = $PSVersionTable.PSVersion
if ($psVersion.Major -lt 5 -or ($psVersion.Major -eq 5 -and $psVersion.Minor -lt 1)) {
    Write-Fail ("PowerShell 5.1 or later is required (found " + $psVersion + ").")
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Fail 'Python 3.12 or later is required and was not found on PATH.'
}
$versionText = ((& python --version 2>&1) -join ' ').Trim()
if ($versionText -match 'Python (\d+)\.(\d+)') {
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 12)) {
        Write-Fail ("Python 3.12 or later is required (found " + $versionText + ").")
    }
}
else {
    Write-Fail ("Cannot determine the Python version: " + $versionText)
}

$hyperv = [bool](Get-Command Get-VM -ErrorAction SilentlyContinue)

if ($Profile) {
    if (-not (Test-Path -LiteralPath $Profile)) {
        Write-Fail ("Profile not found: " + $Profile)
    }
    try {
        Get-Content -LiteralPath $Profile -Raw | ConvertFrom-Json | Out-Null
    }
    catch {
        Write-Fail ("Profile is not valid JSON: " + $Profile)
    }
}
if ($Action -ne 'status' -and -not $Event) {
    Write-Fail ("-Event is required for the " + $Action + " action.")
}
if ($Work -and $Work -match '\s') {
    [Console]::Error.WriteLine("ridge: build path contains spaces; quoting is preserved: " + $Work)
}

if ($CheckOnly) {
    $hypervText = if ($hyperv) { 'available' } else { 'not detected' }
    $profileText = if ($Profile) { 'validated' } else { 'not supplied' }
    Write-Host ("ridge: PowerShell " + $psVersion + "; " + $versionText + "; Hyper-V " + $hypervText + "; profile " + $profileText)
    exit 0
}

$arguments = @('-m', 'ridge.deploy', $Action, '--event', $Event)
if ($Work) { $arguments += @('--work', $Work) }
if ($Provider) { $arguments += @('--provider', $Provider) }
if ($Profile) { $arguments += @('--profile', $Profile) }
if ($Release) { $arguments += @('--release', $Release) }
if ($Destination) { $arguments += @('--destination', $Destination) }
if ($Start) { $arguments += '--start' }

& python @arguments
exit $LASTEXITCODE
