# H01 Receipt (verification slice) — Native-records recovery proven; environment stages named

Date: 2026-09-20. Branch: `chore/h01-verification`. Base: `main`.
Test count: **280 passing** (unchanged; no source changes needed — see below).

## What this slice did

The card's first acceptance step — *"First recover the existing native files with
`expanded.materialize_native` on a second machine or clean environment"* — was
executed locally against the published Git LFS archive:

```text
PYTHONPATH=. python -m expanded.materialize_native --destination work/h01-native-recovery
→ {"verified_originals": 19}
```

- 880 MB archive (`assets/large/native/WS17-native-v1.tar.gz`, real LFS content)
  verified against `assets/native-windows-v1/archive.json` before extraction.
- All 19 original members extracted with per-member size + SHA-256 verification
  against the manifest; `VERIFIED.json` written
  (archive sha256 `ab62411a…6c5762`).
- Derived `memory-layer.local.json` points at the **new** destination's
  `WS17.raw` and the shipped kernel symbols — no original-machine absolute
  paths, no hand-edited scratch files.
- **H01a's PID concern is already satisfied by provenance, not code**: the
  literal PIDs (viewer 6364, parent 7644) exist only inside
  `originals/windows/native-provenance.json` and `observed-processes.json`
  (acquisition records); a repo-wide scan finds no such literals in any
  tooling source. `expanded/prepare.py`'s synthetic fixtures use their own
  parameterized PIDs (4240/3100) by design.
- EVTX sidecars (`Security.evtx.records.json`, `TaskScheduler.evtx.records.json`)
  are published alongside the originals, satisfying the "read EVTX sidecars"
  path without a Windows host.

Caveat: this is the same physical machine that has hosted prior work; the
destination was a fresh directory and the archive/manifest are the published
ones, but a truly clean second machine remains the stronger form of this check
(it pairs naturally with the F05 cold-cache install test on one clean host).

## Consolidation status (verified by reading, no changes needed)

The card's "consolidate preserved recipes" premise is largely already met on
current main: `expanded/materialize_native.py`, `expanded/create_autopsy_case.py`,
`expanded/prepare.py`, `deployment/expanded/build-autopsy-tools.sh` and the
current `configure-image.sh`/`seal-image.sh` are authoritative; the 27
historical recipes are preserved as inert `.txt` with recorded hashes in
`deployment/expanded/build-history/` (with the corrections — libafflib0t64,
generic kernel/NoCloud, fresh credentials/NBD allocation — documented in its
README). No source changes were required in this slice; inventing diffs here
would be churn, not progress.

## Remaining, environment-blocked stages (named)

- **H01b case packaging** — needs a closed Autopsy case directory and Autopsy
  ingest/index verification; the published v2 case archive exists but a fresh
  packaging run is Autopsy-host work.
- **H01c desktop preparation / H01d export + offline boot verification** —
  need a disposable Linux build guest with KVM/NBD and fresh credentials; this
  Windows/Docker Desktop box is not that host, and the card requires a focused
  reviewer for block-device and deletion operations. Blocked, not waived.
- **H01e orchestration** — one build configuration linking stages with
  resumable receipts is the follow-up once H01c/d have a host to run against;
  writing an orchestrator now would be untestable scaffolding.
