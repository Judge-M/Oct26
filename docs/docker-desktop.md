# Container team desktop (Docker-only)

This document describes the proposed container-desktop path for Operation Silent
Ridge: one Docker container per team instead of a per-team Ubuntu VM. It is the
proposed primary desktop design; the [prepared desktop image](desktop-image.md)
(QCOW2/VM) is retained as the fallback.

> Status: documentation only. No container image has been built or run, and the
> container-specific artifacts named here (`deployment/expanded/desktop/Dockerfile`,
> `deployment/expanded/desktop/entrypoint.sh`, `deployment/expanded/compose.desktops.yaml`)
> are not present in this branch. Everything in this document that is not already
> recorded elsewhere in the repository is marked **unverified**. See the design
> proposal `docs/handoff/DOCKER-ONLY-PIVOT.md` (branch `docs/docker-only-pivot`,
> not merged here).

## Architecture

Guacamole's `guacd` already reaches each desktop as plain VNC at
`hostname:5901` on an external `desktop` network. The existing
`deployment/expanded/compose.guacamole.yaml` declares that network
(`desktop: external: true`, `RIDGE_DESKTOP_NETWORK`) and attaches `guacd` to it.
A container that exposes 5901 is therefore a drop-in replacement for the VM.

```text
participant browser
        │ HTTP(S)
        ▼
  Guacamole (HTML5)  ──guacd──►  desktop-teamNN:5901  (VNC, `desktop` network)
        │                             │
        │                             ├─ /evidence, /originals   (read-only volumes)
        │                             ├─ /home/participant/Cases  (per-team volume, seeded)
        │                             └─ Xfce + Autopsy + Cutter + Wireshark + Firefox
        ▼
  IRIS ── CTFd ── integration bridge ── Wazuh ── controller core
        (all containers, internal networks)
```

- One container per team; one shared X display per container, matching the
  intended "three people share a desktop" model.
- VNC is never published to the host. Only `guacd` on the internal `desktop`
  network can reach `desktop-teamNN:5901`. Guacamole terminates the user-facing
  session, so no participant ever connects to VNC directly.
- Central services (IRIS, CTFd, Wazuh, the integration bridge and the controller
  core) are already containers. This path leaves no hypervisor in the design.

## Image contract

The intended image, to be produced by the desktop lane:

| Item | Value |
|---|---|
| Tag | `silent-ridge-desktop:dev` |
| Contents | Ubuntu 24.04 amd64 + Xfce, Autopsy 4.22.0, Sleuth Kit 4.13.0, Cutter 2.5.0 AppImage, Wireshark, Firefox 140.16.0esr, TigerVNC, Thunar, dbus, `tini` |
| Exposed port | `5901` (VNC), reachable only on the `desktop` network |
| PID 1 | `tini` (or equivalent) to reap the VNC/Xfce children |
| Dockerfile | `deployment/expanded/desktop/Dockerfile` — adapts `deployment/expanded/desktop/configure-image.sh` |
| Entry point | `deployment/expanded/desktop/entrypoint.sh` |

Mounts:

| Container path | Mode | Purpose |
|---|---|---|
| `/evidence` | read-only | Released evidence, shared across teams |
| `/originals` | read-only | Original native Windows capture |
| `/home/participant/Cases` | read-write, per-team | Seeded writable copy of the prepared WS17 case |
| `/home/participant/Workspace`, `/home/participant/Scratch` | read-write, per-team | Participant work areas |

Environment and secrets:

- VNC password supplied at runtime as a secret mounted at
  `/etc/silent-ridge/vnc-password` (the same path and format used by the VM
  entrypoint). The container must not start its desktop session until it exists.
- `/etc/silent-ridge/endpoints.json` provides the `iris`, `ctfd` and `wazuh`
  HTTP(S) URLs used by the desktop shortcuts.
- Autopsy/Solr keep the `SOLR_LOGS_DIR` and `SOLR_PID_DIR` handling from
  `configure-image.sh:18-26`; the container needs a matching `shm_size`.

**Unverified:** the Dockerfile, entrypoint, exact base digest, image size and
runtime behaviour have not been built or tested on this branch.

## Build

Intended one-time, online build from the repository root:

```text
docker build -f deployment/expanded/desktop/Dockerfile -t silent-ridge-desktop:dev deployment/expanded/desktop
```

The external build inputs and their verification results are recorded in
[handoff/BUILD-INPUTS.md](handoff/BUILD-INPUTS.md). Build inputs must be staged
into the build context; the image is then saved for offline use (below).

## `compose.desktops.yaml`

`deployment/expanded/compose.desktops.yaml` is the proposed Compose file that
defines N desktop services (`desktop-team01`, `desktop-team02`, …) with their
`desktop` network attachment, per-team volumes, secrets, memory limits and
`shm_size`. Intended usage:

```text
docker compose -f deployment/expanded/compose.desktops.yaml up -d desktop-team01
```

Then start the Guacamole stack and provision one connection whose target is
`desktop-team01:5901` (the Guacamole generator already emits port 5901). Keep
VNC off the host; never publish 5901.

**Unverified:** `compose.desktops.yaml` does not exist in this branch (it is
owned by the desktop/compose lane). The service names, limits and volume layout
above are the proposal, not a tested file.

## Capacity

Autopsy plus Solr is the memory driver.

| Item | Value | Source |
|---|---|---|
| Practical need per Autopsy desktop | ~2–4 GiB | Docker-only pivot proposal §6.4 |
| VM allocation previously tested | 4 vCPU / 8 GiB | `assets/desktop-v1.json` `tested_resources` |
| This PC's Docker engine | ~9.5 GiB RAM | pivot proposal §2.1 |
| Desktops this PC can prove | 1–2 | pivot proposal §6.4 |
| Ten-team event (desktops alone) | ~20–40 GiB | pivot proposal §6.4 |

Ten teams therefore need a **larger or multi-host Docker environment**; the
ten-team load is not supported by a single 32-GiB host or by this workstation.
This is a capacity decision, not a software blocker, and must be settled by
measurement before an event.

## Offline packaging

Build all images online, then export them for the disconnected exercise network:

```text
docker save silent-ridge-desktop:dev | gzip > silent-ridge-desktop-dev.tar.gz
```

Export the central stack and all upstream dependency images the same way.
Publish immutable image digests and an installable manifest alongside the
archives, and load them with `docker load` on the event host. Keep secrets,
credentials and live state outside the image; the image contains no VNC password
or organizer credentials.

## What this path removes from the critical path

Adopting the container desktop removes the following from the critical path
entirely:

- the QCOW2 disk and its per-part assembly,
- `qemu-img` conversion,
- Hyper-V and VirtualBox,
- cloud-init / NoCloud / EC2 metadata handling,
- `seal-image.sh` and the guest-sealing workflow,
- the AWS AMI import path.

The 5.2-GB QCOW2 parts and the VM tooling become an optional fallback rather
than a prerequisite. Everything else in the exercise is already Docker.

## Fallback

The VM path documented in [prepared desktop image](desktop-image.md) and
[offline deployment candidate](expanded-deployment.md) is retained unchanged as
the fallback. Adopting the container as primary is a proposal pending the
decision recorded in `docs/handoff/DOCKER-ONLY-PIVOT.md` §9.

## Caveats

These are known risks from the pivot proposal, not yet tested:

- **Autopsy/Solr** needs `shm_size` and RAM; keep the existing `SOLR_LOGS_DIR`
  and `SOLR_PID_DIR` handling.
- **Firefox sandbox** in a container may need `--no-sandbox` or a seccomp
  profile.
- **Wireshark** opens pcaps fine as non-root; live capture would need `NET_RAW`
  and is not required.
- **Cutter AppImage** runs with `--appimage-extract-and-run`, so no FUSE is
  needed.
- **VNC is unencrypted** — acceptable only on the internal network behind
  Guacamole; never publish 5901.
- **Image size** is roughly 2–4 GB and build time is significant.
- **Fidelity** — a container desktop is not the published VM; record the
  difference and keep the VM path documented as the alternative.
- **Licensing** — Autopsy (Apache-2.0) and Cutter (GPL) are redistributable;
  keep their notices when baking them into the image.
