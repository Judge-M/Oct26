# Thin build/verification launcher. Full event lifecycle is gated in ridge.deploy.
[CmdletBinding()]
param(
    [Parameter(Position=0)][string]$Action = 'status',
    [string]$Component = 'all',
    [string]$Work = 'work/build-receipts'
)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & python -m ridge.deploy $Action --component $Component --work $Work
    $result = $LASTEXITCODE
} finally { Pop-Location }
exit $result
