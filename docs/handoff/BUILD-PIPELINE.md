# Portable build pipeline (H01)

Consolidates the preserved recipes under `deployment/expanded/build-history/` into a
supported, parameterized pipeline. It does not run the archived scripts and does not
depend on the original workstation. Source and deterministic tests run on Windows;
block-device and guest stages require a Linux build host and are reported as blocked
rather than guessed.

## Stages

| Module | Child | Purpose |
|---|---|---|
| `buildpipe/native_records.py` | H01a | Rebuild neutral native records from a materialized `originals/windows` tree. PIDs come from acquisition provenance; timestamps are copied verbatim; raw/source hashes are verified. |
| `buildpipe/case_package.py` | H01b | Package a closed Autopsy case with its released evidence after checking database integrity, completed ingest and a saved keyword index. |
| `buildpipe/desktop.py` | H01c | Disposable guest provider, configurable build root, verified base/tool inputs, fresh credentials and the generic-kernel/NoCloud/Solr fixes. Picks a free NBD device instead of assuming `/dev/nbd0`. |
| `buildpipe/export.py` | H01d | Seal checks, compaction of a stopped owned guest, offline snapshot boot, part splitting and hashing. Validation fields are set only from observed results. |
| `buildpipe/pipeline.py` | H01e | One configuration links the stages; receipts are resumable and the output inventory is immutable. Secrets and the dependency closure stay outside the release root. |

## Configuration

```json
{
  "version": "native-v2",
  "release_root": "work/release",
  "native_source": "work/originals/windows",
  "source_hashes": {"Security.evtx": "<sha256>"},
  "case": {"case": "work/cases/WS17", "evidence": "work/evidence"},
  "desktop": {"build_root": "work/desktop-build"},
  "export": {"image": "work/desktop-build/desktop-build.qcow2"}
}
```

Only the stages present in the configuration run. `work/receipts/<stage>.json` records
a digest of the declared inputs; an unchanged stage is skipped on the next run. Outputs
are immutable: rebuilding changed inputs into an existing release is refused.

## Usage

```text
python -m buildpipe run --config build.json --work work
python -m buildpipe native --source work/originals/windows --destination work/release/native-v2
python -m buildpipe native --export-evtx Security.evtx --destination Security.evtx.records.json
python -m buildpipe case --case work/cases/WS17 --evidence work/evidence \
    --destination work/release/case.tar.gz --manifest work/release/case.json
python -m buildpipe verify-desktop --destination work/release/desktop-v2 --version desktop-v2
```

## Acceptance status

- Reconstructing neutral records and packaging a case from published inputs is covered
  by deterministic tests (`tests/test_buildpipe_*.py`).
- The desktop rebuild, sealing, compaction and offline boot require a disposable Linux
  build host with qemu/nbd. They are implemented but **not executed here**; the
  pipeline marks those stages `blocked` with the missing capability.
- Secrets (`work/secrets/`) and the optional dependency closure (`work/dependencies/`)
  are kept outside `release_root`; the pipeline refuses to publish any release
  containing a known secret marker or build key.
