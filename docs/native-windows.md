# Native Windows training acquisition

The versioned capture in `assets/large/native/WS17-native-v1.tar.gz` was acquired
inside Windows Sandbox. It contains real guest physical memory and exported
Security/Task Scheduler EVTX files. No personal host memory was acquired.
Hashes, original sizes and tool identity are in
`assets/native-windows-v1/archive.json`.

This is a harmless lab reconstruction, **not an acquisition from the historical
incident**. It retains its actual September 15, 2026 UTC timestamps and computer
name. The manifest maps the lab to scenario workstation WS-17. The historical
October incident timeline and its 120-second device offset are unchanged and
must not be applied to the native capture.

The guest ran a compiled `browser.exe` parent surrogate and a harmless
`brief-viewer.exe` child, registered the BriefSync task through Task Scheduler,
and held a TCP connection to a guest-local listener. Sandbox external networking
was disabled. Address 198.51.100.77/32 was assigned to guest loopback; this was
not Internet communication or exfiltration. Both surrogate sources are embedded
in `deployment/expanded/windows/Capture-Guest.ps1`.

## Verified results

- Windows' native event reader parsed process event 4688, record 606, and task
  event 4698, record 607, from the exported Security EVTX.
- Volatility 3 2.28.0 recovered viewer PID 6364, parent PID 7644, the parent name,
  creation time, kernel virtual offset and command line from the raw memory.
- The guest's `Get-NetTCPConnection` snapshot independently recorded the viewer
  connection. The memory connection plugins did **not** validate that endpoint.
  Ticket T16 therefore uses the native live snapshot and does not claim it is a
  memory-derived connection finding.
- Prepared JSON records include source hashes, paths, timestamps, record IDs or
  memory offsets, commands and limitations. Authoring verifies their manifest
  checksums and uses their measured values rather than the old placeholder PIDs.

## Offline use

Extract the archive at `/` inside the isolated desktop (or extract into a new
directory and mount its `originals` directory at `/originals`, read-only).
Prepared records in the Autopsy case reference `/originals/windows/`.
The raw image is about 10.9 GB logically, including unmapped zero-filled ranges;
allow that much extraction space. Its compressed archive is about 880 MB.

`originals/windows/memory-layer.json` contains the CR3 and kernel address recorded
by WinPmem, plus the exact symbol file included in the archive. Automatic page
table detection did not work for this Sandbox capture. On a **preparation host**
with Volatility 3 2.28.0 installed:

```sh
vol --offline -c /originals/windows/memory-layer.json -r json windows.pslist
vol --offline -c /originals/windows/memory-layer.json -r json windows.cmdline --pid 6364 7644
```

Adjust only the two file URIs if using a different preparation-host mount. Do
not modify addresses or the image. Volatility is not installed on participant
desktops; expensive analysis is completed before the event.

## Recreate

Enable Windows Sandbox on Windows 11 Pro and restart if Windows requires it.
No installation ISO is needed. Obtain the pinned vendor production-signed
`go-winpmem_amd64_1.0-rc2_signed.exe` from the URL in the archive manifest.
The launcher checks its SHA-256 before copying it into a fresh, network-disabled
Sandbox with a read-only input share and dedicated writable output share:

```powershell
.\deployment\expanded\windows\New-CaptureSandbox.ps1 `
  -BuildRoot C:\Build\new-native-capture `
  -WinPmemPath C:\Tools\go-winpmem_amd64_1.0-rc2_signed.exe
```

Wait for `output/capture-status.txt` to say `complete`; failures are recorded
separately. Keep originals, source scripts and acquisition logs. Revalidate and
rebuild the prepared records, answers and case whenever a new capture is made:
PIDs, host names, timestamps, hashes and offsets naturally change. Never edit a
native source to force it to match an authored answer. If driver loading fails,
do not disable host security or capture host memory as a workaround.

Sources: [Windows Sandbox architecture](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-architecture),
[WinPmem release](https://github.com/Velocidex/WinPmem/releases/tag/v4.1.dev1),
[Volatility](https://github.com/volatilityfoundation/volatility3).
