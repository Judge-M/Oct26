# Previously local work: disposition

## Preserved in GitHub by this follow-up

| Material | Repository location | Status |
|---|---|---|
| Assessment, execution contract, 30 original task cards and structured dependency inventory | `docs/handoff/` | Current handoff; adds H01 below |
| Cross-machine startup and data recovery procedure | `docs/handoff/CONTINUE-ELSEWHERE.md` | Current instructions |
| 27 preparation, image packaging and validation helpers | `deployment/expanded/build-history/` | Exact historical text and checksum inventory; parameterization tracked by H01 |
| Earlier portable-deployment design and migration notes | `docs/handoff/historical-notes/` | Superseded context; current assessment takes precedence |
| Portable native archive materialization | `expanded/materialize_native.py` | New supported utility; no original-host dependency |

## Already published before this follow-up

- Desktop disk parts and manifest: `assets/large/desktop/`, `assets/desktop-v1.json`.
- Actual Windows memory, EVTX, event XML sidecars, process/connection snapshots, acquisition provenance, exact kernel symbols, completed memory analysis: `assets/large/native/WS17-native-v1.tar.gz`, indexed by `assets/native-windows-v1/archive.json`.
- Prepared neutral records: `assets/native-windows-v1/prepared/`.
- Prepared Autopsy case and initial evidence: `assets/large/autopsy/WS17-prepared-case-v2.tar.gz` and its manifest.
- Training binary/source, fixture generator, native Sandbox acquisition scripts, Autopsy toolchain/case builder, desktop configuration/sealing code and source/tool provenance.

These are the event-content originals. Local extracted copies, assembled disks, WSL installations and duplicate tarballs are not the only copies of any of these assets.

## Deliberately not copied into this handoff

| Local material | Why it is not required to continue elsewhere |
|---|---|
| Temporary SSH private key, known-hosts cache and temporary test passwords | Preparation access only. The published image was sealed. Generate new access for new disposable build guests |
| GitHub credential-helper state and authenticated PR/upload helpers | Personal authentication is not an event artifact. Use the new machine's own GitHub login and standard Git/API tools |
| Partial Windows ISO/download experiments, obsolete test driver and abandoned `New-BuildVMs.ps1` | Unused approaches; accepted capture used Windows Sandbox and the pinned production-signed tool |
| Failed memory connection scans/pool probes and diagnostic logs | No validated finding depended on these. The published record explicitly states that memory connection validation failed; do not turn exploratory output into evidence |
| Raw local CI logs, old patch bundles, duplicate source ZIPs, scratch test folders and one-off PR review cache | Reproducible or superseded by committed source, GitHub CI and the published assessment |
| GUI screenshot and disposable VM runtime state | Useful personal troubleshooting history, not needed to reopen the published tools/case; durable check results are in the artifact manifests |
| Downloaded upstream installers and compiled toolchain caches | Runtime is inside the published desktop; rebuild uses pinned upstream sources/tool versions. Full dependency closure is explicitly still an offline-release task, not a claim that all installer caches are public |

No existing final AWS/event participant credentials were created. Future deployment produces private runtime credentials and state. Those need a separately authorized private backup destination, not a public source commit.

## Remaining portability work

The accepted artifacts can be obtained and used elsewhere now. A completely automated, parameterized **from-source rebuild** of every preparation stage remains H01. This is a documented engineering task; it no longer depends on obtaining hidden scripts from the previous workstation. Complete one-command event deployment remains the original task queue.
