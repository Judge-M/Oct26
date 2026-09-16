# Silent Ridge desktop container

Per-team desktop as a Docker container, an additive replacement for the Ubuntu
24.04 QCOW2 VM described in [docs/desktop-image.md](../../../docs/desktop-image.md).
The VM path and its manifests are unchanged; this image stages the same tools
and launchers and defers every runtime credential to the orchestrator.

## Build

Run from the repository root:

```sh
docker build -f deployment/expanded/desktop/Dockerfile -t silent-ridge-desktop:dev .
```

The build is multi-stage: stage 1 compiles Sleuth Kit 4.13.0 with Java bindings
and stages Autopsy 4.22.0; stage 2 installs the XFCE/TigerVNC runtime, Cutter
2.5.0 and Firefox 140.16.0esr, then installs the participant launchers.

### Required build inputs

Cutter and Firefox are pinned by URL and SHA-256 and verified with `sha256sum -c`
during the build. The values are recorded in
[assets/desktop-container.json](../../../assets/desktop-container.json) and copied
from [assets/desktop-v1.json](../../../assets/desktop-v1.json).

| Input | Version | Pinned |
|---|---|---|
| Ubuntu base | 24.04 | image tag `ubuntu:24.04` |
| Autopsy | 4.22.0 | URL only; SHA-256 not yet recorded |
| Sleuth Kit | 4.13.0 | built from source; SHA-256 not yet recorded |
| Cutter | 2.5.0 | URL + SHA-256 |
| Firefox | 140.16.0esr | URL + SHA-256 |

Autopsy and Sleuth Kit build arguments (`AUTOPSY_SHA256`, `SLEUTHKIT_SHA256`)
default to empty. Supply them with `--build-arg` once the upstream archives have
been verified, so the build fails closed on a changed download. No image build
has been recorded for this Dockerfile; `image_built` stays `false` in the
manifest until one succeeds.

## Run

The container exposes VNC on 5901 for `guacd` only. Never publish 5901 to the
host; attach the container to the internal `desktop` network.

```sh
docker run -d --name ridge-team-01 \
  --network silent-ridge-desktop \
  --mount type=bind,src=/srv/ridge/evidence,dst=/evidence,readonly \
  --mount type=bind,src=/srv/ridge/originals,dst=/originals,readonly \
  --mount type=volume,src=team01-cases,dst=/home/participant/Cases \
  --mount type=volume,src=team01-workspace,dst=/home/participant/Workspace \
  --mount type=volume,src=team01-scratch,dst=/home/participant/Scratch \
  -e IRIS_URL=https://iris.internal/silent-ridge \
  -e CTFD_URL=https://ctfd.internal/silent-ridge \
  -e WAZUH_URL=https://wazuh.internal \
  --secret vnc_password \
  silent-ridge-desktop:dev
```

`docker run --secret` requires Swarm; with Compose use a `secrets:` entry that
mounts the file at `/run/secrets/vnc_password`.

### Runtime contract

- VNC: port 5901, `SecurityTypes VncAuth`, `-AlwaysShared`, never host-published.
- Mounts: `/evidence` (ro), `/originals` (ro), and
  `/home/participant/{Cases,Workspace,Scratch}` (rw).
- Environment: `VNC_PASSWORD_FILE`, `IRIS_URL`, `CTFD_URL`, `WAZUH_URL`.
- Secret: `/run/secrets/vnc_password` is copied to `VNC_PASSWORD_FILE`
  (default `/etc/silent-ridge/vnc-password`, mode 600). The entrypoint fails
  fast if the secret is absent, and `endpoints.json` is generated once from the
  `IRIS_URL`/`CTFD_URL`/`WAZUH_URL` values when it does not already exist.

## Desktop launchers

`configure-desktop.sh` mirrors `configure-image.sh`: it installs
`/opt/silent-ridge/open-service.py` and `/opt/silent-ridge/open-autopsy.sh` and
writes shortcuts for the incident queue, questions and help, Wazuh, evidence,
how-to guides, Autopsy, Wireshark and Cutter
(`--appimage-extract-and-run`). Evidence stays read-only; participant work
belongs in the writable case copy, `Workspace` or `Scratch`.

## Validation

`tests/test_desktop_image.py` statically checks the Dockerfile packages and tool
staging, the entrypoint credential/endpoint/session contract, the launchers and
the manifest pins. It does not build the image or claim a successful build.

```sh
python -m unittest discover -s tests
```
