<#
.SYNOPSIS
    Starts the Windows host services needed by Operation Silent Ridge.

.DESCRIPTION
    This is the non-interactive action used by the installed scheduled task.
    A worker starts OpenSSH and Docker Desktop, waits for Docker, then exits.
    The primary additionally waits for every configured remote Docker context,
    runs the existing idempotent deployment up/start flow, and verifies status.

    The script never builds images, changes a profile, resets an event, removes
    containers or volumes, restores data, or stores a password.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ConfigPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Require-Property {
    param([object]$Object, [string]$Name)
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property -or $null -eq $property.Value -or
            ($property.Value -is [string] -and [string]::IsNullOrWhiteSpace($property.Value))) {
        throw "boot configuration is missing required property '$Name'"
    }
    return $property.Value
}

function Assert-AbsolutePath {
    param([string]$Value, [string]$Name)
    if (-not [IO.Path]::IsPathRooted($Value)) {
        throw "boot configuration property '$Name' must be an absolute path"
    }
}

$resolvedConfig = (Resolve-Path -LiteralPath $ConfigPath).Path
$config = Get-Content -LiteralPath $resolvedConfig -Raw | ConvertFrom-Json
if ((Require-Property $config 'schema_version') -ne 1) {
    throw 'unsupported boot configuration schema_version; expected 1'
}
$role = ([string](Require-Property $config 'role')).ToLowerInvariant()
if ($role -notin @('primary', 'worker')) {
    throw "boot configuration role must be 'primary' or 'worker'"
}

$dockerCli = [string](Require-Property $config 'docker_cli_path')
$dockerDesktop = [string](Require-Property $config 'docker_desktop_path')
$logPath = [string](Require-Property $config 'log_path')
foreach ($entry in @(@($dockerCli, 'docker_cli_path'),
                     @($dockerDesktop, 'docker_desktop_path'),
                     @($logPath, 'log_path'))) {
    Assert-AbsolutePath $entry[0] $entry[1]
}

$logDirectory = Split-Path -Parent $logPath
if (-not $logDirectory) { throw 'log_path must include a parent directory' }
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null

function Write-BootLog {
    param([string]$Message, [ValidateSet('INFO', 'WARN', 'ERROR')][string]$Level = 'INFO')
    $line = '{0} [{1}] {2}' -f ([DateTime]::UtcNow.ToString('o')), $Level, $Message
    Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
    Write-Host $line
}

function ConvertTo-NativeArgument {
    param([AllowEmptyString()][string]$Value)
    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') { return $Value }
    $builder = New-Object Text.StringBuilder
    [void]$builder.Append('"')
    $backslashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq '\') {
            $backslashes++
            continue
        }
        if ($character -eq '"') {
            [void]$builder.Append(('\' * (($backslashes * 2) + 1)))
            [void]$builder.Append('"')
            $backslashes = 0
            continue
        }
        if ($backslashes -gt 0) {
            [void]$builder.Append(('\' * $backslashes))
            $backslashes = 0
        }
        [void]$builder.Append($character)
    }
    if ($backslashes -gt 0) { [void]$builder.Append(('\' * ($backslashes * 2))) }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function Invoke-BoundedProcess {
    param(
        [string]$FilePath,
        [string[]]$Arguments = @(),
        [int]$TimeoutSeconds = 60,
        [switch]$Quiet
    )
    $process = $null
    try {
        $argumentLine = ($Arguments | ForEach-Object { ConvertTo-NativeArgument ([string]$_) }) -join ' '
        # Windows PowerShell 5.1's Start-Process can leave ExitCode null when
        # stdout/stderr are redirected, even after WaitForExit and Refresh.
        # Use ProcessStartInfo directly so readiness checks have a dependable
        # numeric exit code and both streams remain bounded by this process.
        $startInfo = New-Object Diagnostics.ProcessStartInfo
        $startInfo.FileName = $FilePath
        $startInfo.Arguments = $argumentLine
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $process = New-Object Diagnostics.Process
        $process.StartInfo = $startInfo
        if (-not $process.Start()) { throw "could not start process: $FilePath" }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            throw "process exceeded ${TimeoutSeconds}s timeout: $FilePath"
        }
        $process.WaitForExit()
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        $exitCode = $process.ExitCode
        if (-not $Quiet) {
            foreach ($line in (($stdout + "`n" + $stderr) -split "`r?`n")) {
                if (-not [string]::IsNullOrWhiteSpace($line)) { Write-BootLog $line.Trim() }
            }
        }
        return [pscustomobject]@{
            ExitCode = $exitCode
            Stdout = [string]$stdout
            Stderr = [string]$stderr
        }
    } finally {
        if ($null -ne $process) { $process.Dispose() }
    }
}

function Get-DeploymentStatus {
    param(
        [string]$PythonPath,
        [string[]]$CommonArguments,
        [int]$TimeoutSeconds,
        [int]$Attempts,
        [int]$RetrySeconds,
        [string]$Purpose = 'deployment status'
    )
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $result = Invoke-BoundedProcess $PythonPath `
                (@('-m', 'ridge.deploy', 'status') + $CommonArguments) `
                $TimeoutSeconds -Quiet
            if ($result.ExitCode -ne 0) {
                throw "status returned exit code $($result.ExitCode)"
            }
            $document = $result.Stdout | ConvertFrom-Json -ErrorAction Stop
            if ($null -eq $document.PSObject.Properties['journal'] -or
                    [string]::IsNullOrWhiteSpace([string]$document.journal)) {
                throw 'status JSON did not contain a journal state'
            }
            $knownStates = @('NEW', 'RESOURCES_VERIFIED', 'PROVISIONED_PAUSED',
                             'RUNNING', 'STOPPED', 'FENCED', 'DESTROYED')
            if ([string]$document.journal -notin $knownStates) {
                throw "status JSON contained unrecognized journal state '$($document.journal)'"
            }
            return $document
        } catch {
            Write-BootLog "$Purpose attempt $attempt of $Attempts failed: $($_.Exception.Message)" 'WARN'
        }
        if ($attempt -lt $Attempts) { Start-Sleep -Seconds $RetrySeconds }
    }
    throw "$Purpose remained unknown after $Attempts bounded attempts; refusing lifecycle mutation"
}

function Test-DockerContext {
    param([AllowEmptyString()][string]$Context = '')
    $arguments = @()
    if (-not [string]::IsNullOrWhiteSpace($Context)) {
        $arguments += @('--context', $Context)
    }
    $arguments += @('info', '--format', '{{json .ServerVersion}}')
    try {
        $result = Invoke-BoundedProcess $dockerCli $arguments 20 -Quiet
        return $result.ExitCode -eq 0
    } catch {
        return $false
    }
}

function Wait-DockerContext {
    param(
        [AllowEmptyString()][string]$Context,
        [int]$TimeoutSeconds,
        [int]$PollSeconds
    )
    $label = if ([string]::IsNullOrWhiteSpace($Context)) { 'local Docker engine' } else { "Docker context '$Context'" }
    Write-BootLog "waiting up to ${TimeoutSeconds}s for $label"
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-DockerContext $Context) {
            Write-BootLog "$label is ready"
            return
        }
        Start-Sleep -Seconds $PollSeconds
    }
    throw "$label did not become ready within ${TimeoutSeconds}s"
}

function Start-DockerDesktop {
    $service = Get-Service -Name 'com.docker.service' -ErrorAction SilentlyContinue
    if ($service -and $service.Status -ne 'Running') {
        Write-BootLog 'starting com.docker.service'
        Start-Service -Name 'com.docker.service'
    }
    if (Test-DockerContext '') { return }

    # Current Docker Desktop versions expose `docker desktop start`. Fall back
    # to the configured executable for older installations.
    try {
        Write-BootLog 'requesting Docker Desktop startup through the Docker CLI'
        $result = Invoke-BoundedProcess $dockerCli @('desktop', 'start') 90
        if ($result.ExitCode -eq 0) { return }
        Write-BootLog "Docker CLI startup returned exit code $($result.ExitCode); using executable fallback" 'WARN'
    } catch {
        Write-BootLog "Docker CLI startup was unavailable: $($_.Exception.Message)" 'WARN'
    }
    if (-not (Test-Path -LiteralPath $dockerDesktop -PathType Leaf)) {
        throw "Docker Desktop executable not found: $dockerDesktop"
    }
    Write-BootLog 'launching the configured Docker Desktop executable'
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
}

function Ensure-WorkerSsh {
    $sshd = Get-Service -Name 'sshd' -ErrorAction SilentlyContinue
    if (-not $sshd) {
        throw 'Windows OpenSSH service sshd is not installed on this worker'
    }
    if ($sshd.StartType -ne 'Automatic') {
        Set-Service -Name 'sshd' -StartupType Automatic
    }
    if ($sshd.Status -ne 'Running') {
        Write-BootLog 'starting Windows OpenSSH service'
        Start-Service -Name 'sshd'
    }
    $sshd.WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
    Write-BootLog 'Windows OpenSSH service is ready'
}

try {
    Write-BootLog "Silent Ridge boot action started for role '$role'"
    if (-not (Test-Path -LiteralPath $dockerCli -PathType Leaf)) {
        throw "Docker CLI not found: $dockerCli"
    }
    if ($config.PSObject.Properties['docker_config_path'] -and $config.docker_config_path) {
        $dockerConfig = [string]$config.docker_config_path
        Assert-AbsolutePath $dockerConfig 'docker_config_path'
        if (-not (Test-Path -LiteralPath $dockerConfig -PathType Container)) {
            throw "Docker configuration directory not found: $dockerConfig"
        }
        $env:DOCKER_CONFIG = $dockerConfig
    }

    if ($role -eq 'worker') { Ensure-WorkerSsh }
    Start-DockerDesktop

    $pollSeconds = [int](Require-Property $config 'poll_interval_seconds')
    $localTimeout = [int](Require-Property $config 'local_docker_timeout_seconds')
    if ($pollSeconds -lt 1 -or $pollSeconds -gt 60) { throw 'poll_interval_seconds must be between 1 and 60' }
    if ($localTimeout -lt 30 -or $localTimeout -gt 1800) { throw 'local_docker_timeout_seconds must be between 30 and 1800' }
    Wait-DockerContext '' $localTimeout $pollSeconds

    if ($role -eq 'worker') {
        Write-BootLog 'worker boot action completed; Docker and SSH are ready'
        exit 0
    }

    $sourcePath = [string](Require-Property $config 'source_path')
    $pythonPath = [string](Require-Property $config 'python_path')
    $profilePath = [string](Require-Property $config 'profile_path')
    $runtimePath = [string](Require-Property $config 'runtime_path')
    $receiptsPath = [string](Require-Property $config 'build_receipts_path')
    foreach ($entry in @(@($sourcePath, 'source_path'), @($pythonPath, 'python_path'),
                         @($profilePath, 'profile_path'), @($runtimePath, 'runtime_path'),
                         @($receiptsPath, 'build_receipts_path'))) {
        Assert-AbsolutePath $entry[0] $entry[1]
    }
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Container)) { throw "source_path not found: $sourcePath" }
    if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) { throw "python_path not found: $pythonPath" }
    if (-not (Test-Path -LiteralPath $profilePath -PathType Leaf)) { throw "profile_path not found: $profilePath" }
    if (-not (Test-Path -LiteralPath $receiptsPath -PathType Container)) { throw "build_receipts_path not found: $receiptsPath" }

    $remoteTimeout = [int](Require-Property $config 'remote_docker_timeout_seconds')
    if ($remoteTimeout -lt 30 -or $remoteTimeout -gt 1800) { throw 'remote_docker_timeout_seconds must be between 30 and 1800' }
    $contexts = @($config.remote_docker_contexts)
    if ($contexts.Count -eq 0) { throw 'primary boot configuration needs at least one remote_docker_contexts entry' }
    foreach ($context in $contexts) {
        if ([string]::IsNullOrWhiteSpace([string]$context)) { throw 'remote_docker_contexts cannot contain an empty name' }
        Wait-DockerContext ([string]$context) $remoteTimeout $pollSeconds
    }

    $attempts = [int](Require-Property $config 'deployment_attempts')
    $retrySeconds = [int](Require-Property $config 'deployment_retry_seconds')
    $commandTimeout = [int](Require-Property $config 'deployment_command_timeout_seconds')
    $statusAttempts = [int](Require-Property $config 'status_attempts')
    $statusRetrySeconds = [int](Require-Property $config 'status_retry_seconds')
    if ($attempts -lt 1 -or $attempts -gt 12) { throw 'deployment_attempts must be between 1 and 12' }
    if ($retrySeconds -lt 1 -or $retrySeconds -gt 300) { throw 'deployment_retry_seconds must be between 1 and 300' }
    if ($commandTimeout -lt 60 -or $commandTimeout -gt 7200) { throw 'deployment_command_timeout_seconds must be between 60 and 7200' }
    if ($statusAttempts -lt 1 -or $statusAttempts -gt 12) { throw 'status_attempts must be between 1 and 12' }
    if ($statusRetrySeconds -lt 1 -or $statusRetrySeconds -gt 300) { throw 'status_retry_seconds must be between 1 and 300' }

    $common = @('--profile', $profilePath, '--runtime', $runtimePath,
                '--operator', 'boot-automation', '--work', $receiptsPath)
    Push-Location $sourcePath
    try {
        # A second trigger or task retry is a no-op when the event is already
        # healthy and running.
        $initialDocument = Get-DeploymentStatus $pythonPath $common $commandTimeout `
            $statusAttempts $statusRetrySeconds 'initial deployment status'
        if ($initialDocument.journal -eq 'RUNNING' -and $initialDocument.event_ready -eq $true) {
            Write-BootLog 'event is already RUNNING and healthy; no deployment action needed'
            exit 0
        }

        # The registration worker is a host process and is intentionally gone
        # after a reboot, while the durable exercise mode may still say running.
        # Move through the public pause operation so `up` can re-probe its
        # documented PROVISIONED_PAUSED gate before `start` recreates the worker.
        if ($initialDocument.journal -eq 'RUNNING') {
            Write-BootLog 'event journal is RUNNING but not healthy; pausing safely before reconciliation'
            $pause = Invoke-BoundedProcess $pythonPath (@('-m', 'ridge.deploy', 'pause') + $common) $commandTimeout
            if ($pause.ExitCode -ne 0) { throw "deployment pause returned exit code $($pause.ExitCode)" }
            $pausedDocument = Get-DeploymentStatus $pythonPath $common $commandTimeout `
                $statusAttempts $statusRetrySeconds 'post-pause deployment status'
            if ($pausedDocument.journal -notin @('PAUSED', 'PROVISIONED_PAUSED')) {
                throw "post-pause journal state is '$($pausedDocument.journal)'; refusing deployment up"
            }
        }

        $upSucceeded = $false
        for ($attempt = 1; $attempt -le $attempts; $attempt++) {
            Write-BootLog "deployment up attempt $attempt of $attempts"
            try {
                $up = Invoke-BoundedProcess $pythonPath (@('-m', 'ridge.deploy', 'up') + $common) $commandTimeout
                if ($up.ExitCode -eq 0) {
                    $upSucceeded = $true
                    break
                }
                Write-BootLog "deployment up returned exit code $($up.ExitCode)" 'WARN'
            } catch {
                Write-BootLog "deployment up attempt failed: $($_.Exception.Message)" 'WARN'
            }
            if ($attempt -lt $attempts) { Start-Sleep -Seconds $retrySeconds }
        }
        if (-not $upSucceeded) { throw "deployment up failed after $attempts attempts" }

        Write-BootLog 'starting the event through the existing deployment lifecycle'
        $start = Invoke-BoundedProcess $pythonPath (@('-m', 'ridge.deploy', 'start') + $common) $commandTimeout
        if ($start.ExitCode -ne 0) { throw "deployment start returned exit code $($start.ExitCode)" }

        $finalDocument = Get-DeploymentStatus $pythonPath $common $commandTimeout `
            $statusAttempts $statusRetrySeconds 'final deployment status'
        if ($finalDocument.journal -ne 'RUNNING' -or $finalDocument.event_ready -ne $true) {
            throw "final status is not RUNNING/event_ready (journal=$($finalDocument.journal), event_ready=$($finalDocument.event_ready))"
        }
        Write-BootLog 'primary boot action completed; event is RUNNING and event_ready'
    } finally {
        Pop-Location
    }
    exit 0
} catch {
    Write-BootLog $_.Exception.Message 'ERROR'
    Write-BootLog 'boot action failed safely; no reset, teardown, restore, build, or volume removal was attempted' 'ERROR'
    exit 1
}
