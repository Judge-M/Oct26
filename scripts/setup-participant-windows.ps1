<#
.SYNOPSIS
    Prepare a Windows participant workstation for an offline Silent Ridge run.

.DESCRIPTION
    Validates the public event CA and service endpoints, optionally imports the
    public CA into the current user's trust store, creates a private credential
    handoff, and opens the four participant HTTPS services. This script never
    accepts credentials as arguments and never writes them to its console log.

    Trust changes are opt-in and require an interactive confirmation. Use
    -DryRun to validate paths and configuration without changing the machine.
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory = $true)] [string]$Runtime,
    [Parameter(Mandatory = $true)] [string]$CredentialFile,
    [string]$CaFile,
    [string]$Config,
    [string]$OutputDirectory = (Join-Path (Get-Location) 'participant-handoff'),
    [switch]$DryRun,
    [switch]$ImportCertificate,
    [switch]$OpenTabs,
    [switch]$VerifyOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Fail([string]$Message) { throw "participant setup: $Message" }
function Require-File([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { Fail "$Label not found: $Path" }
    return (Resolve-Path -LiteralPath $Path).Path
}
function Read-Config([string]$Path) {
    if (-not $Path) {
        return [ordered]@{
            ctfd = 'https://127.0.0.1:18083'
            iris = 'https://127.0.0.1:18081'
            wazuh = 'https://127.0.0.1:18443'
            guacamole = 'https://127.0.0.1:18082'
        }
    }
    $raw = Get-Content -LiteralPath (Require-File $Path 'config') -Raw | ConvertFrom-Json
    $out = [ordered]@{}
    foreach ($name in 'ctfd','iris','wazuh','guacamole') {
        $value = [string]$raw.$name
        if (-not $value -or $value -notmatch '^https://[^/\s]+(?::\d+)?$') {
            Fail "config.$name must be an HTTPS URL"
        }
        $out[$name] = $value.TrimEnd('/')
    }
    return $out
}
function Get-CertificateFingerprint([string]$Path) {
    $cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($Path)
    try {
        if ($cert.HasPrivateKey) { Fail 'the participant CA contains a private key' }
        if ($cert.NotAfter -le [DateTime]::UtcNow) { Fail 'the participant CA is expired' }
        return [ordered]@{
            Certificate = $cert
            Fingerprint = ($cert.Thumbprint -replace '\s','').ToUpperInvariant()
            Subject = $cert.Subject
            Issuer = $cert.Issuer
            NotAfter = $cert.NotAfter.ToUniversalTime().ToString('o')
        }
    } finally { }
}
function Test-TlsEndpoint([string]$Url, [hashtable]$Ca) {
    $uri = [Uri]$Url
    $port = if ($uri.Port -gt 0) { $uri.Port } else { 443 }
    $client = [Net.Sockets.TcpClient]::new()
    $stream = $null
    try {
        $task = $client.ConnectAsync($uri.DnsSafeHost, $port)
        if (-not $task.Wait(5000) -or -not $client.Connected) { return $false }
        $state = @{ observed = $null; chain_ok = $false }
        $callback = [Net.Security.RemoteCertificateValidationCallback]{
            param($sender, $certificate, $chain, $errors)
            if (-not $certificate) { return $false }
            $state.observed = [Security.Cryptography.X509Certificates.X509Certificate2]::new($certificate)
            $custom = [Security.Cryptography.X509Certificates.X509Chain]::new()
            try {
                $custom.ChainPolicy.ExtraStore.Add($Ca.Certificate) | Out-Null
                $custom.ChainPolicy.VerificationFlags = [Security.Cryptography.X509Certificates.X509VerificationFlags]::AllowUnknownCertificateAuthority
                $custom.Build($state.observed) | Out-Null
                $state.chain_ok = $custom.ChainElements.Count -gt 1
                if ($state.chain_ok) {
                    $root = $custom.ChainElements[$custom.ChainElements.Count - 1].Certificate
                    $state.chain_ok = $root.Thumbprint -eq $Ca.Fingerprint
                }
                # SslStream performs SAN/hostname validation; only the trust-root
                # error may be replaced by the explicit CA check above.
                return $state.chain_ok -and (($errors -band [Net.Security.SslPolicyErrors]::RemoteCertificateNameMismatch) -eq 0) -and (($errors -band [Net.Security.SslPolicyErrors]::RemoteCertificateNotAvailable) -eq 0)
            } finally { $custom.Dispose() }
        }
        $stream = [Net.Security.SslStream]::new($client.GetStream(), $false, $callback)
        $stream.AuthenticateAsClient($uri.DnsSafeHost)
        if (-not $state.observed -or -not $state.chain_ok) { return $false }
        return [ordered]@{ subject = $state.observed.Subject; issuer = $state.observed.Issuer; expires_utc = $state.observed.NotAfter.ToUniversalTime().ToString('o') }
    } catch { return $false } finally {
        if ($stream) { $stream.Dispose() }
        $client.Dispose()
    }
}
function Write-Handoff([string]$Source, [string]$Destination, [hashtable]$Endpoints, [hashtable]$Ca) {
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $target = Join-Path $Destination 'team-credentials.json'
    Copy-Item -LiteralPath $Source -Destination $target -Force
    $acl = Get-Acl -LiteralPath $target
    $acl.SetAccessRuleProtection($true, $false)
    $rule = [Security.AccessControl.FileSystemAccessRule]::new(
        [Security.Principal.WindowsIdentity]::GetCurrent().Name, 'FullControl', 'Allow')
    $acl.SetAccessRule($rule); Set-Acl -LiteralPath $target -AclObject $acl
    $lines = @('Operation Silent Ridge participant handoff', '', 'Credentials: team-credentials.json',
        '', 'Service URLs:')
    foreach ($key in $Endpoints.Keys) { $lines += "- ${key}: $($Endpoints[$key])" }
    $lines += '', "CA fingerprint (SHA-256): $($Ca.Fingerprint)", "CA subject: $($Ca.Subject)",
        "CA expires (UTC): $($Ca.NotAfter)", '', 'The credential file is private. Do not email or commit it.'
    Set-Content -LiteralPath (Join-Path $Destination 'README.txt') -Value $lines -Encoding UTF8
    return $target
}

$runtimePath = (Resolve-Path -LiteralPath $Runtime -ErrorAction SilentlyContinue)
if (-not $runtimePath) { Fail "runtime directory not found: $Runtime" }
$defaultCa = Join-Path $runtimePath.Path 'wazuh-certs\root-ca.cer'
if (-not (Test-Path -LiteralPath $defaultCa -PathType Leaf)) {
    $defaultCa = Join-Path $runtimePath.Path 'wazuh-certs\root-ca.pem'
}
$caPath = Require-File $(if ($CaFile) { $CaFile } else { $defaultCa }) 'public CA certificate'
$credentialPath = Require-File $CredentialFile 'credential file'
$endpoints = Read-Config $Config
$ca = Get-CertificateFingerprint $caPath

if ((Get-Item -LiteralPath $credentialPath).Length -eq 0) { Fail 'credential file is empty' }
$endpointResults = [ordered]@{}
foreach ($key in $endpoints.Keys) { $endpointResults[$key] = Test-TlsEndpoint $endpoints[$key] $ca }
$failed = @($endpointResults.GetEnumerator() | Where-Object { -not $_.Value } | ForEach-Object Key)
if ($failed.Count -gt 0) { Fail "unreachable HTTPS endpoint(s): $($failed -join ', ')" }

if ($ImportCertificate -and -not $DryRun) {
    if (-not $PSCmdlet.ShouldProcess('CurrentUser\TrustedRootCertificationAuthorities',
            "Import verified CA $($ca.Fingerprint)")) { Fail 'CA import was not confirmed' }
    $importPath = $caPath
    $temporaryDer = $null
    try {
        if ([IO.Path]::GetExtension($caPath).ToLowerInvariant() -eq '.pem') {
            $temporaryDer = Join-Path ([IO.Path]::GetTempPath()) ("silent-ridge-ca-" + [Guid]::NewGuid().ToString('N') + '.cer')
            [IO.File]::WriteAllBytes($temporaryDer, [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($caPath).Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert))
            $importPath = $temporaryDer
        }
        Import-Certificate -FilePath $importPath -CertStoreLocation 'Cert:\CurrentUser\Root' | Out-Null
    } finally {
        if ($temporaryDer -and (Test-Path -LiteralPath $temporaryDer)) { Remove-Item -LiteralPath $temporaryDer -Force }
    }
}

$handoff = if ($DryRun -or $VerifyOnly) { $null } else {
    Write-Handoff $credentialPath $OutputDirectory $endpoints $ca
}
if ($OpenTabs -and -not $DryRun -and -not $VerifyOnly) {
    foreach ($url in $endpoints.Values) { Start-Process $url | Out-Null }
}

[ordered]@{
    dry_run = [bool]$DryRun
    ca_fingerprint = $ca.Fingerprint
    ca_subject = $ca.Subject
    ca_expires_utc = $ca.NotAfter
    endpoints_verified = $endpointResults
    ca_imported = [bool]($ImportCertificate -and -not $DryRun)
    handoff_path = $handoff
    tabs_requested = [bool]($OpenTabs -and -not $DryRun -and -not $VerifyOnly)
} | ConvertTo-Json -Compress
