# Versioned exercise assets

Track small, fictional exercise inputs and documentation here. Place reviewed
large evidence, closed prepared cases and desktop images in `assets/large/` using
Git LFS. Install Git LFS before adding them (`git lfs install`). The directory is
an explicit exception to the image/database rules in `.gitignore`; runtime
databases and team exports remain excluded elsewhere.

Do not add real credentials, participant data, active cases or event backups.
All fictional exercise content, including answers and future-release evidence,
is intentionally published from this repository. Participant access to GitHub
is accepted by the event owner. Runtime release gating still controls the normal
exercise experience; repository secrecy is not a requirement.

A prepared Autopsy 4.22.0 case is supplied in
`large/autopsy/WS17-prepared-case-v2.tar.gz`, with checksums and verification
results in `autopsy-case-v2.json`. It includes the FAT disk image, released
logical evidence, compiled training binary, and saved keyword index. Both
sources completed ingest; the database passed its integrity check and the
case reopened successfully after relocation.

Extract the archive into a new directory on the Linux participant desktop.
Mount its `evidence` directory read-only at `/evidence`, then open the `.aut`
file under `cases/` using Autopsy 4.22.0. Keep a writable case copy per team.
The `/evidence` path is required because Autopsy stores absolute source paths.
Do not share one writable case database between teams.

Rebuild using `deployment/expanded/build-autopsy-tools.sh`, then run
`expanded/create_autopsy_case.py` as a non-root Linux user with `--autopsy`,
`--evidence /evidence`, and a new `--output` directory. The builder selects
Linux-supported modules and verifies completed ingest and the saved index.

The case also includes source-referenced records from an acquired Windows Sandbox
memory image and native EVTX. The originals are in
`large/native/WS17-native-v1.tar.gz`; extract them at `/originals/windows`.
See [native provenance and limitations](../docs/native-windows.md). Acquisition
timestamps remain separate from the historical incident timeline. T16 uses a
live connection snapshot; that connection was not recovered from memory.
The version-one case remains available for provenance; use version two for the
native-record questions. The desktop image includes these originals and the case.
Validate the complete bundle with `ridge.artifacts` before declaring an
event-ready release.

Git LFS has plan-dependent object limits and storage/bandwidth costs. For objects
that exceed those limits, use appropriately sized GitHub Release assets and record
every part and checksum in the manifest. Never commit a giant blob to ordinary Git.
