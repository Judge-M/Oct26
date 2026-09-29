<#
.SYNOPSIS
    One-command, repeatable Windows participant install for an event runtime.

.DESCRIPTION
    Runs the repository's verified participant setup, imports the event CA when
    needed, creates the protected credential handoff, and optionally opens the
    four service tabs. Re-running the command is safe: an already trusted CA is
    detected by fingerprint and is not imported or prompted for again.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$Runtime,
    [Parameter(Mandatory = $true)] [string]$CredentialFile,
    [string]$CaFile,
    [string]$Config,
    [string]$OutputDirectory = (Join-Path (Get-Location) 'participant-handoff'),
    [switch]$OpenTabs,
    [switch]$DryRun,
    [switch]$VerifyOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'setup-participant-windows.ps1'
if (-not (Test-Path -LiteralPath $script -PathType Leaf)) {
    throw "participant setup script not found: $script"
}

$args = @{
    Runtime = $Runtime
    CredentialFile = $CredentialFile
    OutputDirectory = $OutputDirectory
    ImportCertificate = $true
    Confirm = $false
}
if ($CaFile) { $args.CaFile = $CaFile }
if ($Config) { $args.Config = $Config }
if ($OpenTabs) { $args.OpenTabs = $true }
if ($DryRun) { $args.DryRun = $true }
if ($VerifyOnly) { $args.VerifyOnly = $true }

& $script @args
exit $LASTEXITCODE
