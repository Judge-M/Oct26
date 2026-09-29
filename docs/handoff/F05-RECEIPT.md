# F05 Receipt (independent slice) — Atomic offline-bundle installer

Date: 2026-09-20. Branch: `feat/f05-offline-installer`. Base: `main` (PRs #30/#31 merged).
Test count: **280 passing** (266 + 14 installer tests).

## Blocked prerequisites (named per card)

F05 lists **E02, E04, D03, C04, F04**. **E04 (AWS infrastructure) is blocked**
(no AWS account/credentials on this machine; organizer has deferred AWS until
after the local release). Per the card's finish-and-stop rule, this turn
completes only independent source/test work. Additionally, the card requires
capacity/restore gates to be linked before `compatibility_verified` /
`event_ready` are set — **F03 (capacity) and F06 (dress rehearsal) remain open**,
so this slice deliberately does **not** produce a certified complete bundle or
flip those flags.

## What exists already (verified by reading)

- `ridge/artifacts.py` — fail-closed manifest/hash verification with the full
  required-kind set and an `--allow-incomplete` inspection mode.
- `ridge/bundle.py` — assembles an offline bundle from a validated store:
  immutable image IDs only, source/image hash cross-checks run in a
  networkless read-only container, `docker save` of exact identities,
  `SHA256SUMS.json` over the result.
- `ridge/distribution.py` — GitHub release packaging with immutable GHCR
  digest locks; rejects LFS stubs and mutable tags.

## Gap found and closed in this slice

The bundle had **no installer**: consumers were left to reconstruct archives
and load images by hand — exactly what the card forbids ("do not leave users
copying asset-NNNN.bin files manually"; "make source installation/
materialization automatic and atomic").

**`ridge/offline_install.py`** (new) installs a bundle:

1. **Verify** — every file hashed against `SHA256SUMS.json` (which cannot list
   itself; exclusion documented), manifest checked via `artifacts.verify`;
   missing parts, extra files, corruption and **LFS pointer stubs** each fail
   with the offending path named. Uncertified bundles install with the
   certification gap recorded in the receipt (`certified_complete: false`),
   never silently waived.
2. **Preflight** — free disk must cover extraction plus image-load working
   space; the error names required vs available bytes and happens before any
   write.
3. **Atomic staging** — source and the (reassembled) image archive stage in a
   sibling `.staging` directory and `os.replace` into place only when
   complete; interruption or docker failure leaves **no** partial destination
   and rerunning is always safe.
4. **Bounded parts** — `validated-images.tar` may be a single file or a
   `validated-images.tar.part-NNN` series; gaps in the series are rejected;
   parts are reassembled before `docker load`. (Producer-side splitting in
   `bundle.pack` is the remaining follow-up; the installer contract is now
   fixed.)
5. **Load + receipt** — every manifest image ID must be present after
   `docker load`; the receipt records release, source commit, image IDs,
   certification status and the exact next commands.

**`tests/test_offline_install.py`** — 14 tests: happy path, missing/corrupt
parts named, LFS stub rejection, uncertified-gap recording, single vs split
archive detection, part-gap rejection, reconstruction + receipt, `--no-load`,
existing-destination refusal, low-disk preflight (no staging left behind),
interruption atomicity, post-load missing-image detection, preflight byte
reporting.

## What remains for F05 (not done here)

- **GHCR publishing** of custom and upstream images (needs a release decision
  and registry credentials; externally visible, so left for the release turn).
- **Producer-side bounded splitting** in `bundle.pack` (installer contract
  already supports it).
- **Cold-cache, no-Internet install on a clean host** — requires a fresh
  machine or VM; this machine is the build host, not a clean cache.
- **`compatibility_verified` / `event_ready`** — stays false until F03 and F06
  close, per the card.
