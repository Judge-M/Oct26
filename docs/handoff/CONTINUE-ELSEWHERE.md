# Continue on another computer

You do not need the original Windows computer, its WSL distribution, its build SSH key, or its temporary VNC password to continue development. The finished content is in Git LFS. This handoff and the historical preparation recipes are now in the repository too.

Until this follow-up PR is merged, use branch `docs/portable-build-handoff`; afterwards use `main`.

## Get the project

Install Git, Git LFS and Python 3.12+ on the new machine, then:

```text
git clone --branch docs/portable-build-handoff https://github.com/Judge-M/Oct26.git
cd Oct26
git lfs install
git lfs pull
python -m unittest discover -s tests -v
```

This downloads several gigabytes. For source-only work, clone with Git LFS smudging disabled, then fetch only the binary needed by fixture tests:

```text
git lfs pull --include="assets/large/binary/**" --exclude=""
```

Use `GIT_LFS_SKIP_SMUDGE=1` in the clone environment for that source-only option (PowerShell: `$env:GIT_LFS_SKIP_SMUDGE='1'`; remove it after cloning). A pointer file is not an acquired image; fetch the other artifacts before using them.

Start with [execution contract](EXECUTION.md) and [task queue](TASKS.md). Assign one card under `tasks/` at a time. Read [local-work inventory](LOCAL-WORK-INVENTORY.md) for what was preserved and why some scratch material was excluded.

## Recover the prepared content

```text
python -m ridge.desktop_image --destination work/desktop.qcow2
python -m expanded.materialize_native --verify-only
python -m expanded.materialize_native --destination work/native-preparation
```

The first command reconstructs the existing desktop. The native command verifies the published archive and every original during extraction; it needs approximately 11 GB plus reserve. It creates a separate local Volatility configuration with file URIs appropriate to the new machine and preserves the original configuration. `VERIFIED.json` is written only when extraction succeeds. A failed extraction is removed; existing destinations are never replaced.

The extracted `originals/windows/` contains the actual memory, EVTX, XML sidecars, native snapshots, provenance, symbols and completed process-analysis JSON. The desktop already contains these originals and a writable case copy. To use the standalone case, fetch/extract `assets/large/autopsy/WS17-prepared-case-v2.tar.gz` and follow `docs/desktop-image.md` and `docs/native-windows.md`.

The accepted capture is fixed evidence. A new capture will have different PIDs, timestamps, offsets and hashes; never reuse old measured values blindly. Do not regenerate it merely because you changed development computers.

## What environment is required for which work?

| Work | Required environment |
|---|---|
| Core changes, fixtures, handoff work | Python 3.12+, Git; fixture binary from LFS |
| Reusing existing desktop | QEMU/KVM, or validated conversion/provider work described by C01/E03 |
| Reopening the prepared case | Published desktop, or matching Autopsy 4.22.0 / SleuthKit 4.13.0 / Java/OpenJFX Linux environment |
| Re-running memory analysis | Preparation host with Volatility 3 2.28.0, extracted original and bundled symbols; use `memory-layer.local.json` |
| Creating a new native acquisition | Windows Sandbox and the pinned production-signed acquisition tool; published Windows scripts explain setup |
| Complete event deployment | Still requires the implementation/acceptance tasks in this handoff |

## Rebuild source and history

Supported entrypoints already in source: `expanded/prepare.py`, `expanded/author.py`, `expanded/create_autopsy_case.py`, `deployment/expanded/build-autopsy-tools.sh`, `deployment/expanded/windows/`, and the desktop configuration/sealing scripts.

Additional original build/packaging/validation helpers are preserved under `deployment/expanded/build-history/`. They are **non-executable historical text**, not a finished portable build pipeline. Their README maps old paths to recoverable inputs and records superseded steps. Task **H01** turns them into a supported parameterized pipeline. No future agent needs to retrieve these recipes from the previous computer.

The older design notes in `historical-notes/` are retained context, not current acceptance evidence. The assessment and task cards take precedence where they disagree.
