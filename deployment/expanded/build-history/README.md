# Preserved preparation recipes

These 27 original scripts were previously only in the preparation workspace. Their bytes and hashes are recorded in `inventory.json`. They are saved as `.txt` so imports, test discovery and casual execution cannot run commands against hardcoded disks/VMs or overwrite version-one evidence.

**Do not rename and run them as a batch.** They capture the actual build process, including intermediate states that later scripts corrected. The published artifact manifests and current production scripts are authoritative. This directory preserves enough engineering context to continue on another machine; it does not claim a fully portable or bit-reproducible image builder.

## Recipe groups

| Recipes | Purpose / dependencies |
|---|---|
| `prepare_native_assets.py`, `package_native.py` | Derive neutral records and archive originals; input EVTX XML, process analysis, acquisition metadata and exact symbols all exist in the published native archive |
| `run_memory.py`, `analyze_memory.py`, `check_memory_records.py` | Capture-specific Volatility investigation; prefer the validated published `memory-layer.json` and completed analysis. Automatic detection and memory connection validation did not succeed |
| `build_binary_asset.py` | Compile the harmless surrogate and record provenance; source is `expanded/binary/brief-viewer-training.c` |
| `package_case.py`, `package_case_v2.py`, `inspect_case.py`, `resume_case.py` | Closed-case packaging and validation; v2 is current, v1 is historical. Use the current `expanded/create_autopsy_case.py` for fresh ingest |
| `download_ubuntu.py`, `inspect_media.py`, `boot_desktop.py`, `fix_desktop_boot.sh` | Original base image and NoCloud build setup; exact base URL/hash is in `assets/desktop-v1.json` |
| `transfer_desktop.py`, `update_desktop_content.py`, `desktop_copy.py`, `desktop_exec.py` | Stage tools/content and access a disposable guest; generate a NEW preparation SSH key and use your own guest address/port |
| `desktop_generic_boot.sh`, `test_desktop.sh`, `read_desktop_screen.py`, `verify_desktop_search.py` | Kernel change and actual GUI/search checks; the test VNC password is generated, never embedded |
| `export_desktop.py`, `compact_desktop.py`, `fix_desktop_hyperv_wait.py`, `check_export_boot.py`, `package_desktop.py` | Seal inspection, zero free blocks, compress, remove Hyper-V-only startup waits, boot an offline snapshot, split and hash the final disk |

## Replace original-machine assumptions

- `/mnt/c/Users/mj777/Documents/Codex/2026-09-14/i/work/Oct26-fixes` means the checked-out repository, not a required location.
- `/opt/silent-ridge-build` means a disposable Linux preparation root. Recreate tool installations from the published builder and package/tool versions; it contains no irreplaceable event content.
- `windows-capture/output` is recoverable as `originals/windows` using `python -m expanded.materialize_native`. Completed memory analysis is inside its `analysis/` subdirectory. The original raw checksum is in the published manifest; a scratch `native/memory.sha256` file is not required evidence.
- `memory-resolved.json` was the local precursor of the published `memory-layer.json`; use the generated `memory-layer.local.json` for new paths.
- `native-case-v2/cases/...` is a fresh build output from `expanded/create_autopsy_case.py`, or use the published closed v2 case. Old `repro-case-*` directories are intermediate builds, not missing downloads.
- `/evidence` and `/originals` inside the participant desktop are intentional artifact contracts. Do not replace those paths in the distributed case without testing source relocation.
- `build-key`, `known-hosts`, guest IPs, NBD device, mount directory and process IDs are preparation resources to allocate anew, never values to recover from the old computer.

## Corrections that must survive a new builder

The initial boot recipe requested `libafflib0v5`; the validated Ubuntu 24.04 installation uses **libafflib0t64**. The initial source image used an Azure kernel/datasource; the validated guest uses generic **6.8.0-139-generic**, NoCloud/EC2, disabled Azure and Hyper-V-specific daemons. Source image extension `.vhd` did not establish its actual disk format; inspect with `qemu-img info`.

Use the current Autopsy launcher with participant-writable Solr log/PID directories. Use current `configure-image.sh` and `seal-image.sh`, not intermediate copies. The source C file is canonical LF; the original compiler input used CRLF, recorded separately in `assets/training-binary.json`. No binary change is implied by that normalization.

Verify the final compressed disk after all offline edits and boot a snapshot without altering the sealed base. Publish parts/manifests only after success. Never apply block-device, recursive-delete, shutdown or guest-sealing commands to a personal/event host.

Next implementation work: [H01](../../../docs/handoff/tasks/H01.md).
