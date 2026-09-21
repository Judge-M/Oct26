# F05b Receipt — Real offline bundle assembled and install-verified

Date: 2026-09-21. Branch: `feat/f05-bundle-parts`. Base: `main` (through PR #36).
Test count: **284 passing** (280 + 4 split/contract tests).

## What was built

- **`ridge/bundle.py`** —
  - `split_file()`: producer-side bounded parts. `validated-images.tar` is split
    under `--max-part-bytes` into `validated-images.tar.part-NNN`; the naming
    contract is the exact one `ridge.offline_install.image_parts` consumes
    (round-trip test proves ordering and byte-preserving reassembly).
  - `--allow-incomplete`: builds a **drill bundle** only when the manifest has
    `compatibility_verified: false`, and stamps
    `certification: drill-uncertified` into the bundle manifest. The certified
    path is unchanged and still requires `compatibility_verified: true`
    (awaiting the F03/F06 gates — not set here, honestly).
- **`scripts/assemble_offline_store.py`** — reproducible store assembly:
  gathers the published large artifacts (desktop qcow2 parts, native capture,
  prepared Autopsy case), tars the generated asset trees (evidence-public,
  case-template + wazuh-config, guides), resolves immutable image IDs from the
  local Docker daemon (no hardcoded digests), and emits the release manifest
  pinned to the current commit.

## The real drill bundle (built on this machine)

`work/offline-bundle/` — **14.2 GB**, release `silent-ridge-expanded-1`,
source commit `29bcb08`, `certification: drill-uncertified`:

- `source.zip` (6.0 GB — git archive includes real LFS content, so the source
  tree is self-contained), cross-checked image sources
  (`source-image-checks.json`);
- `validated-images.tar.part-001..003` (2 GiB + 2 GiB + 1.8 GiB) — 13 images:
  the four custom images (integration/iris/ctfd **rebuilt from this HEAD**,
  new image IDs; desktop unchanged inputs) plus postgres, mariadb, redis,
  rabbitmq, the three Wazuh images, guacamole/guacd;
- desktop qcow2 parts, native capture (880 MB), prepared case v2, FAT16 disk
  evidence, evidence/dependencies/guides trees;
- `release-manifest.json` + `SHA256SUMS.json`.

## Verification actually performed

1. `python -m ridge.offline_install work/offline-bundle work/offline-installed
   --no-load` — every byte of all 14.2 GB hashed against SHA256SUMS, manifest
   verified, split parts reassembled, source reconstructed (5.8 GB).
   Receipt: `certified_complete: false`, gap named ("compatibility not
   verified") — recorded, not waived.
2. **Atomicity under kill**: a second full install was interrupted at 300 s by
   the tool timeout mid-`docker load`; the destination was never created and
   only the `.staging` directory remained — exactly the designed behavior
   (cleaned up afterwards).
3. `docker load` of the reassembled 6 GB archive streamed without error (it
   exceeds 300 s on this daemon because layers already exist and are
   re-verified); afterwards all **13 manifest image IDs confirmed present**.

Not done (unchanged from F05 receipt): GHCR publishing, and the cold-cache
no-Internet install on a genuinely clean host — this bundle is now the input
for exactly that test.
