param([Parameter(Mandatory=$true)][string]$BuildRoot,
      [Parameter(Mandatory=$true)][string]$WinPmemPath)
$ErrorActionPreference = 'Stop'
$expected = '86691bb4af2c17dd9ec4834c04a99ad51e04f780a07d1b05bc382a5d1892e0c4'
if ((Get-FileHash -LiteralPath $WinPmemPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
    throw 'Supply the pinned vendor production-signed go-winpmem_amd64_1.0-rc2_signed.exe; see native-windows.md.'
}
if (Test-Path -LiteralPath $BuildRoot) { throw 'Choose a new capture directory; existing evidence is never overwritten.' }
$root = [IO.Path]::GetFullPath($BuildRoot)
New-Item -ItemType Directory -Path "$root\input","$root\output" | Out-Null
Copy-Item -LiteralPath $WinPmemPath -Destination "$root\input\winpmem.exe"
Copy-Item -LiteralPath "$PSScriptRoot\Capture-Guest.ps1" -Destination "$root\input\Capture-Guest.ps1"
$inputPath = [Security.SecurityElement]::Escape("$root\input")
$outputPath = [Security.SecurityElement]::Escape("$root\output")
@"
<Configuration>
  <VGpu>Disable</VGpu><Networking>Disable</Networking>
  <ClipboardRedirection>Disable</ClipboardRedirection><MemoryInMB>4096</MemoryInMB>
  <MappedFolders>
    <MappedFolder><HostFolder>$inputPath</HostFolder><SandboxFolder>C:\CaptureInput</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
    <MappedFolder><HostFolder>$outputPath</HostFolder><SandboxFolder>C:\CaptureOutput</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder>
  </MappedFolders>
  <LogonCommand><Command>powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\CaptureInput\Capture-Guest.ps1</Command></LogonCommand>
</Configuration>
"@ | Set-Content -LiteralPath "$root\capture.wsb" -Encoding UTF8
Start-Process -FilePath "$env:WINDIR\System32\WindowsSandbox.exe" -ArgumentList ('"'+$root+'\capture.wsb"') -WindowStyle Hidden
Write-Output "Capture started. Check $root\output\capture-status.txt; retain originals and review before publication."
