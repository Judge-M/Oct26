> Historical proposal/inventory from PRs 14/18. Current instructions: [BUILD-FIRST.md](BUILD-FIRST.md).
> Do not treat old host capability claims, missing hashes or design decisions below as current acceptance.

# Desktop image build inputs — verification record

Checked **2026-09-16** from this workstation with PowerShell
`Invoke-WebRequest -Method Head` (reachability, size, last-modified) and
`Get-FileHash -Algorithm SHA256` (recorded checksums). This covers the one-time,
online build inputs for the proposed container desktop
([docker-desktop.md](../docker-desktop.md)); the same tools also apply to the VM
fallback.

All four canonical URLs below returned HTTP **200**. No URL was unreachable.

## Results

| Input | Version | URL | Recorded sha256 | HTTP check (2026-09-16) |
|---|---|---|---|---|
| Cutter AppImage | 2.5.0 | `https://github.com/rizinorg/cutter/releases/download/v2.5.0/Cutter-v2.5.0-Linux-x86_64.AppImage` | `b8ad215d7a9e2af9e1f463511229f16e1f4745a0fb541413e5f4787f949ac0cf` | 200 OK · 144,423,416 bytes (137.7 MiB) · Last-Modified Tue, 30 Jun 2026 18:08:18 GMT |
| Firefox ESR | 140.16.0esr | `https://archive.mozilla.org/pub/firefox/releases/140.16.0esr/linux-x86_64/en-US/firefox-140.16.0esr.tar.xz` | `a90174f8fecfb1767371015a625a2f7ffc1edafd9110717348e797a46a066edf` | 200 OK · 75,357,768 bytes (71.9 MiB) · Last-Modified Mon, 14 Sep 2026 13:12:55 GMT |
| Autopsy (Linux) | 4.22.0 | `https://github.com/sleuthkit/autopsy/releases/download/autopsy-4.22.0/autopsy-4.22.0.zip` **(not recorded in repo)** | **not recorded** | 200 OK · 1,247,202,394 bytes (1.16 GiB) · Last-Modified Tue, 11 Mar 2025 20:04:43 GMT |
| Sleuth Kit | 4.13.0 | `https://github.com/sleuthkit/sleuthkit/releases/download/sleuthkit-4.13.0/sleuthkit-4.13.0.tar.gz` **(not recorded in repo; see git source below)** | **not recorded** | 200 OK · 4,575,895 bytes (4.36 MiB) · Last-Modified Mon, 10 Mar 2025 18:35:45 GMT |

## What is recorded in the repository

- **Cutter 2.5.0** — URL and sha256 recorded in `assets/desktop-v1.json:57-58`.
  Downloaded and re-hashed: computed SHA-256 matched the recorded value.
- **Firefox 140.16.0esr** — URL and sha256 recorded in
  `assets/desktop-v1.json:62-63`. Downloaded and re-hashed: computed SHA-256
  matched the recorded value.
- **Autopsy 4.22.0 (Linux)** — `assets/desktop-v1.json:53` records the version
  string only. `deployment/expanded/build-autopsy-tools.sh:4` expects the official
  `autopsy-4.22.0.zip` via the `AUTOPSY_ZIP` environment variable but does not
  record a URL or checksum. The GitHub release URL above is the canonical
  upstream location; it is **not** recorded in this repository and no recorded
  hash exists to compare against. It is unverified against a repository record.
- **Sleuth Kit 4.13.0** — `assets/desktop-v1.json:54` records the version string
  only. `deployment/expanded/build-autopsy-tools.sh:15` records the source as
  `https://github.com/sleuthkit/sleuthkit.git` at tag `sleuthkit-4.13.0` (a git
  clone, not a tarball). No checksum is recorded anywhere. The release tarball
  URL above is the canonical upstream location; it is not recorded in this
  repository.
- For reference, a GET of the Sleuth Kit tarball on 2026-09-16 produced
  SHA-256 `f1490de8487df8708a4287c0d03bf0cb2153a799db98c584ab60def5c55c68f2`.
  This is a **measured** value, not a recorded or upstream-published one; treat
  it as provisional until an official checksum is recorded.

The Ubuntu base image URL and sha256 in `assets/desktop-v1.json:48-50` belong to
the QCOW2/VM fallback and are not required by the container path.

## Commands used

```powershell
$urls = @(
  'https://github.com/rizinorg/cutter/releases/download/v2.5.0/Cutter-v2.5.0-Linux-x86_64.AppImage',
  'https://archive.mozilla.org/pub/firefox/releases/140.16.0esr/linux-x86_64/en-US/firefox-140.16.0esr.tar.xz',
  'https://github.com/sleuthkit/autopsy/releases/download/autopsy-4.22.0/autopsy-4.22.0.zip',
  'https://github.com/sleuthkit/sleuthkit/releases/download/sleuthkit-4.13.0/sleuthkit-4.13.0.tar.gz'
)
foreach ($u in $urls) {
  $r = Invoke-WebRequest -Uri $u -Method Head -MaximumRedirection 10 -UseBasicParsing -TimeoutSec 60
  "{0} {1} {2} {3}" -f $u, $r.StatusCode, $r.Headers['Content-Length'], $r.Headers['Last-Modified']
}
```

```powershell
# Recorded-hash verification (Cutter and Firefox)
Invoke-WebRequest -Uri $cutterUrl  -OutFile Cutter.AppImage
Invoke-WebRequest -Uri $firefoxUrl -OutFile firefox.tar.xz
(Get-FileHash Cutter.AppImage  -Algorithm SHA256).Hash
(Get-FileHash firefox.tar.xz   -Algorithm SHA256).Hash
```

## Notes and limitations

- HEAD checks confirm reachability, reported size and last-modified only. They do
  not verify a download against a checksum; the Cutter and Firefox entries above
  were separately downloaded and hashed to confirm the recorded values.
- GitHub release URLs redirect to short-lived `release-assets.githubusercontent.com`
  URLs. Record and pin the **checksum**, not the signed redirect.
- Autopsy and Sleuth Kit have no repository-recorded checksum. Add the official
  values to the artifact manifest before an offline build; do not substitute the
  measured Sleuth Kit hash for an official one.
- The Autopsy archive is large (~1.16 GiB) and was not downloaded here, so no
  local hash was computed for it.
