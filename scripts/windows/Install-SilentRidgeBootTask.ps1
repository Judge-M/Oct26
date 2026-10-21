<#
.SYNOPSIS
    Installs or updates the Silent Ridge Windows boot scheduled task.

.DESCRIPTION
    Run once as a Windows administrator on each event server. The task account
    credential is requested at install time and stored by Windows Task Scheduler;
    it is never written to the repository, configuration, action arguments, or
    log. A separate InteractiveToken task runs after the selected account signs
    in, which is the reliable Docker Desktop fallback. Re-running this installer
    replaces the same tasks and installed files.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Primary', 'Worker')]
    [string]$Role,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ConfigPath,

    [PSCredential]$TaskCredential,

    [switch]$CurrentUserInteractive,

    [ValidateNotNullOrEmpty()]
    [string]$InstallRoot = "$env:ProgramData\SilentRidge\boot"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this one-time installer from an elevated PowerShell window.'
}
if (-not [IO.Path]::IsPathRooted($ConfigPath)) {
    throw 'ConfigPath must be an absolute path.'
}
$resolvedConfig = (Resolve-Path -LiteralPath $ConfigPath).Path
$config = Get-Content -LiteralPath $resolvedConfig -Raw | ConvertFrom-Json
if ($config.schema_version -ne 1) { throw 'Configuration schema_version must be 1.' }
if ([string]$config.role -ne $Role.ToLowerInvariant()) {
    throw "Configuration role '$($config.role)' does not match installer role '$Role'."
}

$forbiddenNames = @($config.PSObject.Properties.Name | Where-Object {
    $_ -match '(?i)(password|passphrase|private.?key|secret|token|credential)'
})
if ($forbiddenNames.Count -gt 0) {
    throw "Boot configuration must not contain secrets; remove: $($forbiddenNames -join ', ')"
}
$required = @('docker_cli_path', 'docker_desktop_path', 'docker_config_path',
              'log_path', 'poll_interval_seconds', 'local_docker_timeout_seconds')
if ($Role -eq 'Primary') {
    $required += @('remote_docker_timeout_seconds', 'remote_docker_contexts',
                   'source_path', 'python_path', 'profile_path', 'runtime_path',
                   'build_receipts_path', 'deployment_attempts',
                   'deployment_retry_seconds', 'deployment_command_timeout_seconds',
                   'status_attempts', 'status_retry_seconds')
}
foreach ($name in $required) {
    $property = $config.PSObject.Properties[$name]
    if ($null -eq $property -or $null -eq $property.Value -or
            ($property.Value -is [string] -and [string]::IsNullOrWhiteSpace($property.Value))) {
        throw "Boot configuration is missing required property '$name'."
    }
}
foreach ($name in @('docker_cli_path', 'docker_desktop_path', 'docker_config_path', 'log_path')) {
    if (-not [IO.Path]::IsPathRooted([string]$config.$name)) {
        throw "Boot configuration property '$name' must be an absolute path."
    }
}
if (-not (Test-Path -LiteralPath ([string]$config.docker_cli_path) -PathType Leaf)) {
    throw "Docker CLI not found: $($config.docker_cli_path)"
}
if (-not (Test-Path -LiteralPath ([string]$config.docker_desktop_path) -PathType Leaf)) {
    throw "Docker Desktop executable not found: $($config.docker_desktop_path)"
}
if (-not (Test-Path -LiteralPath ([string]$config.docker_config_path) -PathType Container)) {
    throw "Docker configuration directory not found: $($config.docker_config_path)"
}
if ($Role -eq 'Primary') {
    foreach ($name in @('source_path', 'python_path', 'profile_path', 'runtime_path',
                         'build_receipts_path')) {
        if (-not [IO.Path]::IsPathRooted([string]$config.$name)) {
            throw "Boot configuration property '$name' must be an absolute path."
        }
    }
    foreach ($name in @('source_path', 'runtime_path', 'build_receipts_path')) {
        if (-not (Test-Path -LiteralPath ([string]$config.$name) -PathType Container)) {
            throw "Configured directory not found for '$name': $($config.$name)"
        }
    }
    foreach ($name in @('python_path', 'profile_path')) {
        if (-not (Test-Path -LiteralPath ([string]$config.$name) -PathType Leaf)) {
            throw "Configured file not found for '$name': $($config.$name)"
        }
    }
    if (@($config.remote_docker_contexts).Count -eq 0) {
        throw 'Primary configuration requires at least one remote Docker context.'
    }
}

$workerSshd = $null
if ($Role -eq 'Worker') {
    $workerSshd = Get-Service -Name 'sshd' -ErrorAction SilentlyContinue
    if (-not $workerSshd) { throw 'Worker installation requires the Windows OpenSSH sshd service.' }
}

if ($CurrentUserInteractive -and $TaskCredential) {
    throw 'CurrentUserInteractive cannot be combined with TaskCredential.'
}
if (-not $CurrentUserInteractive -and -not $TaskCredential) {
    $TaskCredential = Get-Credential -Message 'Windows account that owns Docker Desktop and the configured Docker contexts'
}
$taskUser = if ($CurrentUserInteractive) { $identity.Name } else { $TaskCredential.UserName }
if ([string]::IsNullOrWhiteSpace($taskUser)) { throw 'A task account is required.' }

$sourceScript = Join-Path $PSScriptRoot 'Start-SilentRidgeBoot.ps1'
if (-not (Test-Path -LiteralPath $sourceScript -PathType Leaf)) {
    throw "Boot action script is missing: $sourceScript"
}
if (-not [IO.Path]::IsPathRooted($InstallRoot)) { throw 'InstallRoot must be an absolute path.' }

$startupTaskName = "Silent Ridge - $Role Boot"
$logonTaskName = "Silent Ridge - $Role Logon"
$installedScript = Join-Path $InstallRoot 'Start-SilentRidgeBoot.ps1'
$installedConfig = Join-Path $InstallRoot ("{0}.json" -f $Role.ToLowerInvariant())
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

if ($PSCmdlet.ShouldProcess("$startupTaskName / $logonTaskName", 'install or update Windows automation')) {
    New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
    Copy-Item -LiteralPath $sourceScript -Destination $installedScript -Force
    Copy-Item -LiteralPath $resolvedConfig -Destination $installedConfig -Force

    # The task account needs to read its installed config and append to the
    # configured log. Administrators and SYSTEM retain recovery access.
    & icacls.exe $InstallRoot '/inheritance:r' '/grant:r' `
        '*S-1-5-18:(OI)(CI)(F)' '*S-1-5-32-544:(OI)(CI)(F)' `
        "${taskUser}:(OI)(CI)(M)" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not secure install directory $InstallRoot" }

    $startupArguments = '-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -ConfigPath "{1}"' -f `
        $installedScript, $installedConfig
    $interactiveArguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "{0}" -ConfigPath "{1}"' -f `
        $installedScript, $installedConfig
    $startupAction = New-ScheduledTaskAction -Execute $powershell -Argument $startupArguments
    $interactiveAction = New-ScheduledTaskAction -Execute $powershell -Argument $interactiveArguments
    $startupTrigger = New-ScheduledTaskTrigger -AtStartup
    $startupTrigger.Delay = 'PT30S'
    $logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $taskUser
    $logonTrigger.Delay = 'PT30S'

    # Cover the complete worst-case envelope for one boot action. Task Scheduler
    # restart attempts are separate executions and each receives this full limit.
    $worstCaseSeconds = 120 + [int]$config.local_docker_timeout_seconds
    if ($Role -eq 'Primary') {
        $statusEnvelope = ([int]$config.status_attempts * [int]$config.deployment_command_timeout_seconds) +
            (([int]$config.status_attempts - 1) * [int]$config.status_retry_seconds)
        $upEnvelope = ([int]$config.deployment_attempts * [int]$config.deployment_command_timeout_seconds) +
            (([int]$config.deployment_attempts - 1) * [int]$config.deployment_retry_seconds)
        $remoteEnvelope = @($config.remote_docker_contexts).Count * [int]$config.remote_docker_timeout_seconds
        # Initial status, worst-case pause, post-pause status, up retries, start,
        # final status, and a fifteen-minute scheduling/process margin.
        $worstCaseSeconds += $remoteEnvelope + (3 * $statusEnvelope) +
            [int]$config.deployment_command_timeout_seconds + $upEnvelope +
            [int]$config.deployment_command_timeout_seconds + 900
    } else {
        $worstCaseSeconds += 300
    }
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew -RestartCount 5 `
        -RestartInterval (New-TimeSpan -Minutes 2) `
        -ExecutionTimeLimit (New-TimeSpan -Seconds $worstCaseSeconds)

    if ($CurrentUserInteractive) {
        # Interactive-only mode deliberately removes a stale password-backed
        # startup task. Docker Desktop is then guaranteed only after this user
        # signs in and the InteractiveToken task starts.
        if (Get-ScheduledTask -TaskName $startupTaskName -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $startupTaskName -Confirm:$false
        }
    } else {
        $plainPassword = $TaskCredential.GetNetworkCredential().Password
        try {
            Register-ScheduledTask -TaskName $startupTaskName -Action $startupAction `
                -Trigger $startupTrigger -Settings $settings `
                -Description "Operation Silent Ridge $Role startup automation" `
                -User $TaskCredential.UserName -Password $plainPassword -RunLevel Highest -Force | Out-Null
        } finally {
            $plainPassword = $null
        }
    }

    # This is a distinct InteractiveToken principal, not a password-logon task
    # with an AtLogOn trigger. It can interact with the signed-in user's Docker
    # Desktop session and never needs a stored password.
    $interactivePrincipal = New-ScheduledTaskPrincipal -UserId $taskUser `
        -LogonType Interactive -RunLevel Highest
    Register-ScheduledTask -TaskName $logonTaskName -Action $interactiveAction `
        -Trigger $logonTrigger -Settings $settings -Principal $interactivePrincipal `
        -Description "Operation Silent Ridge $Role interactive Docker Desktop fallback" `
        -Force | Out-Null

    # These services must survive a reboot. The action still verifies and starts
    # them so a delayed service is logged clearly.
    $dockerService = Get-Service -Name 'com.docker.service' -ErrorAction SilentlyContinue
    if ($dockerService) { Set-Service -Name 'com.docker.service' -StartupType Automatic }
    if ($Role -eq 'Worker') {
        Set-Service -Name 'sshd' -StartupType Automatic
    }

    if (-not $CurrentUserInteractive) {
        Write-Host "Installed startup task:  $startupTaskName"
    } else {
        Write-Host 'Startup task omitted: current-user interactive mode requires sign-in.'
    }
    Write-Host "Installed logon task:    $logonTaskName"
    Write-Host "Installed action:        $installedScript"
    Write-Host "Installed configuration: $installedConfig"
    Write-Host "Per-execution time limit: $worstCaseSeconds seconds (covers the configured worst case plus margin)."
    Write-Host 'The logon task uses InteractiveToken and retries failures five times.'
    Write-Host 'Docker Desktop is guaranteed after sign-in; startup-before-sign-in requires a successful cold-boot acceptance test.'
    Write-Host 'No password was written to the repository, configuration, task arguments, or log.'
}
