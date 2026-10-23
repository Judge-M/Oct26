[CmdletBinding()]
param(
    [string]$SourceRoot = 'C:\Oct26\source-e881666',
    [string]$InitialRuntime = 'C:\Oct26\event-runtime-live11-20261021',
    [string]$ActiveRuntimeFile = 'C:\Oct26\active-rehearsal-runtime.txt'
)

$ErrorActionPreference = 'Stop'
$PasswordSha256 = 'eab97514e6ec29e4bbe85dbaea651488926caef3932e82fc11b2c14ed7987e72'

function Show-Message([string]$Text, [string]$Title, [System.Windows.Forms.MessageBoxIcon]$Icon) {
    [void][System.Windows.Forms.MessageBox]::Show(
        $Text, $Title, [System.Windows.Forms.MessageBoxButtons]::OK, $Icon)
}

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    $arguments = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $PSCommandPath),
        '-SourceRoot', ('"{0}"' -f $SourceRoot),
        '-InitialRuntime', ('"{0}"' -f $InitialRuntime),
        '-ActiveRuntimeFile', ('"{0}"' -f $ActiveRuntimeFile)
    )
    Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList $arguments
    exit 0
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = [System.Windows.Forms.Form]::new()
$form.Text = 'Reset Silent Ridge Rehearsal'
$form.StartPosition = 'CenterScreen'
$form.Size = [Drawing.Size]::new(440, 265)
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.MinimizeBox = $false

$intro = [System.Windows.Forms.Label]::new()
$intro.Location = [Drawing.Point]::new(20, 15)
$intro.Size = [Drawing.Size]::new(395, 55)
$intro.Text = "This archives the current rehearsal, resets event data, and starts a clean rehearsal ready for team registration.`r`nFacilitator login: admin / Access4n/a"
$form.Controls.Add($intro)

$userLabel = [System.Windows.Forms.Label]::new()
$userLabel.Location = [Drawing.Point]::new(20, 82)
$userLabel.Size = [Drawing.Size]::new(90, 24)
$userLabel.Text = 'Username'
$form.Controls.Add($userLabel)
$username = [System.Windows.Forms.TextBox]::new()
$username.Location = [Drawing.Point]::new(120, 79)
$username.Size = [Drawing.Size]::new(275, 24)
$username.Text = 'admin'
$form.Controls.Add($username)

$passLabel = [System.Windows.Forms.Label]::new()
$passLabel.Location = [Drawing.Point]::new(20, 122)
$passLabel.Size = [Drawing.Size]::new(90, 24)
$passLabel.Text = 'Password'
$form.Controls.Add($passLabel)
$password = [System.Windows.Forms.TextBox]::new()
$password.Location = [Drawing.Point]::new(120, 119)
$password.Size = [Drawing.Size]::new(275, 24)
$password.UseSystemPasswordChar = $true
$form.Controls.Add($password)

$reset = [System.Windows.Forms.Button]::new()
$reset.Location = [Drawing.Point]::new(120, 168)
$reset.Size = [Drawing.Size]::new(165, 36)
$reset.Text = 'Archive and reset'
$reset.DialogResult = [System.Windows.Forms.DialogResult]::OK
$form.AcceptButton = $reset
$form.Controls.Add($reset)

$cancel = [System.Windows.Forms.Button]::new()
$cancel.Location = [Drawing.Point]::new(295, 168)
$cancel.Size = [Drawing.Size]::new(100, 36)
$cancel.Text = 'Cancel'
$cancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$form.CancelButton = $cancel
$form.Controls.Add($cancel)

if ($form.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 0 }
$sha = [Security.Cryptography.SHA256]::Create()
$enteredHash = ([BitConverter]::ToString(
    $sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($password.Text)))).Replace('-', '').ToLowerInvariant()
if ($username.Text -cne 'admin' -or $enteredHash -cne $PasswordSha256) {
    Show-Message 'The username or password is incorrect.' 'Reset not started' ([System.Windows.Forms.MessageBoxIcon]::Error)
    exit 1
}

$runtime = $InitialRuntime
if (Test-Path -LiteralPath $ActiveRuntimeFile) {
    $candidate = (Get-Content -LiteralPath $ActiveRuntimeFile -Raw).Trim()
    if ($candidate) { $runtime = $candidate }
}
$runtime = [IO.Path]::GetFullPath($runtime)
$source = [IO.Path]::GetFullPath($SourceRoot)
if (-not $runtime.StartsWith('C:\Oct26\event-runtime-', [StringComparison]::OrdinalIgnoreCase)) {
    Show-Message "Refusing unexpected runtime path: $runtime" 'Reset not started' ([System.Windows.Forms.MessageBoxIcon]::Error)
    exit 2
}
$profile = Join-Path $runtime 'registration-profile.json'
$local = Join-Path $runtime 'local.json'
$keyFile = Join-Path $runtime 'secrets\recovery-backup-key.txt'
foreach ($required in @($profile, $local, $keyFile, (Join-Path $source 'ridge.ps1'))) {
    if (-not (Test-Path -LiteralPath $required)) {
        Show-Message "Required reset file is missing: $required" 'Reset not started' ([System.Windows.Forms.MessageBoxIcon]::Error)
        exit 2
    }
}

# Prove every image is the reviewed build before changing the live run.  This
# prevents a source edit or stale worker image from being discovered only after
# the old rehearsal has already been archived.
$receiptSource = 'C:\Oct26\build-receipts-e881666'
$receiptTarget = Join-Path $source 'work\build-receipts'
New-Item -ItemType Directory -Path $receiptTarget -Force | Out-Null
Copy-Item -Path (Join-Path $receiptSource '*.json') -Destination $receiptTarget -Force
Push-Location $source
& python -m ridge.deploy verify-build --component all --work $receiptSource | Out-Null
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Show-Message 'Reset did not start because the reviewed images are stale. Ask the event administrator to rebuild all four images.' 'Reset not started' ([System.Windows.Forms.MessageBoxIcon]::Error)
    exit 2
}
Pop-Location
$desktopReceipt = Get-Content (Join-Path $receiptSource 'desktop.json') -Raw | ConvertFrom-Json
$hostConfig = Get-Content -LiteralPath $local -Raw | ConvertFrom-Json
foreach ($worker in @($hostConfig.desktop_workers.PSObject.Properties.Value)) {
    $workerImage = (& docker --context $worker.docker_context image inspect silent-ridge-desktop:dev --format '{{.Id}}' 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or $workerImage -ne $desktopReceipt.image_id) {
        Show-Message "Reset did not start because worker $($worker.docker_context) does not have the reviewed desktop image." 'Reset not started' ([System.Windows.Forms.MessageBoxIcon]::Error)
        exit 2
    }
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$archive = "$runtime-archive-$stamp"
$logDir = 'C:\Oct26\rehearsal-reset-logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir "reset-$stamp.log"

try {
    Start-Transcript -Path $log -Force | Out-Null
    $env:RIDGE_BACKUP_KEY = (Get-Content -LiteralPath $keyFile -Raw).Trim()
    Push-Location $source
    $journalPath = Join-Path $runtime 'deploy-journal.sqlite'
    $statePath = Join-Path $runtime 'state\state.sqlite'
    if (-not (Test-Path -LiteralPath $journalPath) -or
        -not (Test-Path -LiteralPath $statePath)) {
        & .\ridge.ps1 up -Profile $profile -Runtime $runtime -Operator 'facilitator-reset'
        if ($LASTEXITCODE -ne 0) { throw 'Could not resume the clean rehearsal setup.' }
        & .\ridge.ps1 start -Profile $profile -Runtime $runtime -Operator 'facilitator-reset'
        if ($LASTEXITCODE -ne 0) { throw 'The clean rehearsal was prepared, but registration could not be started.' }
        Pop-Location
        [IO.File]::WriteAllText($ActiveRuntimeFile, $runtime)
        Show-Message "Reset recovery complete.`r`n`r`nClean rehearsal: $runtime`r`nTeam registration is open and the rehearsal is running." 'Silent Ridge ready' ([System.Windows.Forms.MessageBoxIcon]::Information)
        exit 0
    }
    & .\ridge.ps1 pause -Profile $profile -Runtime $runtime -Operator 'facilitator-reset'
    if ($LASTEXITCODE -ne 0) { throw 'Could not pause the rehearsal.' }
    & .\ridge.ps1 backup -Profile $profile -Runtime $runtime -Operator 'facilitator-reset'
    if ($LASTEXITCODE -ne 0) { throw 'Could not create and verify the recovery set.' }
    & python -m ridge.deploy down --volumes --profile $profile --runtime $runtime --operator 'facilitator-reset'
    if ($LASTEXITCODE -ne 0) { throw 'Could not remove the event-owned volumes.' }
    Pop-Location

    $profileText = Get-Content -LiteralPath $profile -Raw
    $localText = Get-Content -LiteralPath $local -Raw
    $keyText = Get-Content -LiteralPath $keyFile -Raw
    Move-Item -LiteralPath $runtime -Destination $archive
    New-Item -ItemType Directory -Path (Join-Path $runtime 'secrets') -Force | Out-Null
    [IO.File]::WriteAllText((Join-Path $runtime 'registration-profile.json'), $profileText)
    [IO.File]::WriteAllText((Join-Path $runtime 'local.json'), $localText)
    [IO.File]::WriteAllText((Join-Path $runtime 'secrets\recovery-backup-key.txt'), $keyText)
    Push-Location $source
    & .\ridge.ps1 up -Profile (Join-Path $runtime 'registration-profile.json') -Runtime $runtime -Operator 'facilitator-reset'
    if ($LASTEXITCODE -ne 0) { throw 'The archived run is safe, but the clean rehearsal did not start.' }
    & .\ridge.ps1 start -Profile (Join-Path $runtime 'registration-profile.json') -Runtime $runtime -Operator 'facilitator-reset'
    if ($LASTEXITCODE -ne 0) { throw 'The clean rehearsal was prepared, but registration could not be started.' }
    Pop-Location
    [IO.File]::WriteAllText($ActiveRuntimeFile, $runtime)
    Show-Message "Reset complete.`r`n`r`nClean rehearsal: $runtime`r`nArchived run: $archive`r`nTeam registration is open and the new rehearsal is running." 'Silent Ridge ready' ([System.Windows.Forms.MessageBoxIcon]::Information)
} catch {
    try { Pop-Location } catch {}
    Show-Message ("Reset stopped safely: {0}`r`n`r`nLog: {1}" -f $_.Exception.Message, $log) 'Reset needs attention' ([System.Windows.Forms.MessageBoxIcon]::Error)
    exit 1
} finally {
    Remove-Item Env:RIDGE_BACKUP_KEY -ErrorAction SilentlyContinue
    try { Stop-Transcript | Out-Null } catch {}
}
