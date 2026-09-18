# Build first, then run

Run from the repository root using Python 3.12+, Git LFS, and Docker with Linux
containers. WSL alone is not a Docker engine. On an existing Docker workstation,
use its engine; do not install a second engine or a new hypervisor unnecessarily.

## 1. Inspect and recover content

```text
git status --short
git rev-parse HEAD
git lfs version
python --version
python -m ridge.deploy doctor
git lfs pull --include="assets/large/binary/**,assets/large/autopsy/**" --exclude=""
python -m unittest discover -s tests
python -m ridge.case_template --destination work/case-template
```

The case-template command verifies the published v2 archive before extracting it.
Use a fresh destination; never overwrite a participant's existing case. The full
native originals are fetched separately with `git lfs pull
--include="assets/large/native/**" --exclude=""`, then verified/extracted using
`python -m expanded.materialize_native --destination work/native-preparation`.
The published VM can still be assembled using `ridge.desktop_image`; it is not
needed to build the additional Docker desktop image.

## 2. Actually build the images

```text
python -m ridge.deploy build --component iris
python -m ridge.deploy build --component ctfd
python -m ridge.deploy build --component integration
python -m ridge.deploy build --component desktop
python -m ridge.deploy verify-build
```

Windows wrapper: `./ridge.ps1 build -Component desktop`. Build receipts record
image IDs and input fingerprints in `work/build-receipts`. Failed builds remove
the previous success receipt. Changed source or a changed image invalidates it.
Builds need online dependency access; they are preparation, not an offline event
installer. Final image digests and a complete offline dependency bundle are later
release gates. Do not remove `pull_policy: never` to mask a missing runtime image.

## 3. Smoke test the built desktop

On a disposable Linux Docker worker, from the same checkout:

```text
bash tests/desktop_container_smoke.sh
```

This verifies the image receipt, mounts the real verified case template, starts
Xfce offline, checks tool executables/native libraries, and verifies that a restart
preserves case work. CI runs the build before this script. A passing smoke is not
yet a Guacamole session, an Autopsy keyword-search acceptance, or a ten-team test.

Runtime mounts: released evidence `/evidence` read-only; native originals
`/originals` read-only; verified case template `/opt/silent-ridge/prepared-case`
read-only; each team's Cases/Workspace/Scratch in separate writable volumes.
The VNC secret is plaintext input at `/run/secrets/vnc_password`; startup encodes
it into a separate TigerVNC password file. Never set output equal to the secret.

## 4. Integrate the central services

Use NEXT.md task N1. Build success does not configure identities, certificates,
volumes or Wazuh. Generate a private runtime environment from the validated
profile, discover IDs after bootstrap, and leave the core paused. Do not manually
invent IDs merely to get preflight past an error. The historical manual recipe in
LOCAL-SETUP-FINDINGS.md records discoveries, not the final deployment procedure.

`python -m ridge.deploy up/start/backup/restore/switch/down` deliberately refuses
until the missing full lifecycle is implemented and accepted. `status` reports
the outstanding gate. Do not bypass that boundary.
